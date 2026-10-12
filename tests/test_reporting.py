import base64
from copy import deepcopy
from datetime import date
from pathlib import Path
import re
import unittest
from unittest.mock import patch
from xml.etree import ElementTree

from streamlit.testing.v1 import AppTest
from components.reporting import activity_svg, icon, kpi_html, statuses_html, svg_image
from services.business_data_service import load_store
from services.reporting_service import PERIODS, period_bounds, snapshot
from request_fixtures import valid_choices

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 10, 12)


class ReportingTests(unittest.TestCase):
    def test_known_kpi_formulas_and_codex003(self):
        source = load_store()
        request = dict(source['demandes'][0], **valid_choices())
        request.update(RequestReference='DEM-000001', RequestDate='2026-10-08', RequestStatus='En cours')
        order = dict(source['interventions'][0], WorkOrderReferenceEnrobEau='INT-000001',
                     RequestReference='DEM-000001', WorkOrderStatus='Clôturée', ClosedAt='2026-10-10')
        other_order = dict(order, WorkOrderReferenceEnrobEau='INT-000002', WorkOrderReferenceSaur='WO-OTHER', ClosedAt='2026-10-11')
        service = dict(source['prestations'][0], ServiceReference='PR-000001',
                       WorkOrderReferenceEnrobEau='INT-000001', ServiceStatus='En cours',
                       ExcavationDate='2026-10-08', BackfillDate='2026-10-09',
                       HasConcrete2Cm=None, Concrete2CmDate=None, HasTemporaryRepair=True,
                       TemporaryRepairDate='2026-10-09', FinalRepairDate=None)
        store = dict(demandes=[request], interventions=[order, other_order],
                     prestations=[service, dict(service, ServiceReference='PR-000002')])
        data = snapshot(store, period='Dernier mois', today=TODAY)
        self.assertEqual(data['metrics'], (1, 2, 2, 2.5, 100))
        request.update(RequestReason='Renouvellement de branchement', MeterReference=None)
        data = snapshot(store, period='Dernier mois', today=TODAY)
        self.assertEqual(data['metrics'][4], 0)
        self.assertIn('Matricule Compteur', data['rows'][0]['conformity_errors'][0])

    def test_existing_data_join_grains_and_no_mutation(self):
        store = load_store()
        before = deepcopy(store)
        for period in PERIODS:
            for city in ['Toutes les communes', 'Saint-Chamond', 'Inexistante']:
                data = snapshot(store, city, period, TODAY)
                ids = {r['reference'] for r in data['rows']}
                expected_orders = [o for o in store['interventions'] if o['RequestReference'] in ids]
                self.assertEqual(data['orders'], expected_orders)
                order_ids = {o['WorkOrderReferenceEnrobEau'] for o in expected_orders}
                self.assertEqual(data['services'], [s for s in store['prestations'] if s['WorkOrderReferenceEnrobEau'] in order_ids])
                self.assertEqual(sum(data['statuses']), len(ids))
                self.assertEqual(sum(data['cities'].values()), len(ids))
                self.assertEqual(sum(r['requests'] for r in data['activity']), data['metrics'][0])
                self.assertEqual(sum(r['completed'] for r in data['activity']), data['metrics'][1])
        self.assertEqual(store, before)

    def test_calendar_boundaries_and_empty_period(self):
        self.assertEqual(period_bounds('Dernière semaine', TODAY), (date(2026, 10, 6), TODAY))
        self.assertEqual(period_bounds('Dernier mois', TODAY), (date(2026, 9, 13), TODAY))
        self.assertEqual(period_bounds('Dernier mois', date(2024, 3, 31))[0], date(2024, 3, 1))
        self.assertEqual(period_bounds('12 derniers mois', TODAY)[0], date(2025, 10, 13))
        self.assertEqual(snapshot(load_store(), 'Inexistante', today=TODAY)['metrics'], (0, 0, 0, None, None))

    def test_siblings_do_not_inflate_request_count(self):
        store = load_store()
        baseline = snapshot(store, today=TODAY)
        extra = dict(store['prestations'][0], ServiceReference='PR-999999')
        store['prestations'].append(extra)
        data = snapshot(store, today=TODAY)
        self.assertEqual(data['metrics'][:2], baseline['metrics'][:2])
        self.assertEqual(len(data['rows']), len(baseline['rows']))
        self.assertEqual(len(data['locations']), len(baseline['locations']))

    def test_svg_images_have_namespace_and_kpi_icons(self):
        data = snapshot(load_store(), today=TODAY)
        self.assertEqual(kpi_html(data).count('<img '), 6)
        for html in (icon('file'), svg_image(activity_svg(data['activity'])), statuses_html(data)):
            payload = re.search(r'base64,([^\"]+)', html).group(1)
            self.assertEqual(ElementTree.fromstring(base64.b64decode(payload)).tag, '{http://www.w3.org/2000/svg}svg')

    def test_page_and_new_period_controls(self):
        with patch('services.reporting_service.recent_photos', return_value=[]):
            app = AppTest.from_file(str(ROOT / 'pages/reporting_collectivite.py'))
            app.session_state['current_user'] = dict(actif=True, profil='agent', initials='EP')
            app.run(timeout=30)
            self.assertFalse(app.exception)
            self.assertIn('Dernier mois', app.selectbox(key='reporting_period').options)
            app.selectbox(key='reporting_period').select('Dernière semaine').run(timeout=30)
            self.assertFalse(app.exception)

    def test_denied_profiles_stop_before_loading(self):
        for user in ({}, dict(actif=True, profil='agent externe'), dict(actif=False, profil='agent')):
            with patch('services.business_data_service.load_store') as load:
                app = AppTest.from_file(str(ROOT / 'pages/reporting_collectivite.py'))
                app.session_state['current_user'] = user
                app.run(timeout=30)
                self.assertFalse(app.exception)
                self.assertTrue(app.error)
                load.assert_not_called()
