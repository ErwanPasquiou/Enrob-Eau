"""Reporting collectivité calculé à partir des données métier de l'application."""
import streamlit as st

from components.header import render_header
from components.page_content import create_page_content
from components.reporting import kpi_html, render_charts, followup_html, render_recent_photos
from components.styles import load_css
from services.access_service import require_page
from services.business_data_service import load_store
from services.reporting_service import PERIODS, snapshot, city_names, awaiting_repair

user = require_page("reporting")
load_css("reporting.css")
render_header(active_page="Reporting", initials=user.get("initials", ""),
              show_admin=user.get("profil") == "administrateur")
try:
    store = load_store()
except (OSError, ValueError) as exc:
    st.error(f"Impossible de charger les données du reporting : {exc}")
    st.stop()

with create_page_content():
    _, content, _ = st.columns([.5, 24, .5], gap="small")
    with content:
        st.html('<div class="reporting-root"></div>')
        title, city_column, period_column = st.columns([3.6, 1.2, 1], vertical_alignment="center")
        with title:
            st.html('<div class="rp-heading"><h1>Reporting collectivité</h1><p>Pilotez l’activité Enrob’Eau sur votre territoire grâce à des indicateurs consolidés.</p></div>')
        cities = ["Toutes les communes", *city_names(store)]
        if st.session_state.get("reporting_city") not in cities:
            st.session_state["reporting_city"] = "Toutes les communes"
        city = city_column.selectbox("Collectivité", cities, key="reporting_city")
        period = period_column.selectbox("Période", list(PERIODS), key="reporting_period")
        data = snapshot(store, city, period)
        st.html(f'<p class="rp-demo">Données de l’application · demandes du {data["start"]:%d/%m/%Y} au {data["end"]:%d/%m/%Y}</p>')

        overview, performance, dossiers, photos, export = st.tabs(["Vue d’ensemble", "Performance", "Dossiers", "Photos", "Export"])
        with overview:
            st.html(kpi_html(data))
            render_charts(data)
            priority_column, photos_column = st.columns([2.18, 1], gap="small")
            with priority_column, st.container(border=True):
                st.html('<h2 class="rp-section-title">Dossiers à suivre</h2>')
                orders = {o["WorkOrderReferenceEnrobEau"]: o for o in data["orders"]}
                waiting_ids = {orders[s["WorkOrderReferenceEnrobEau"]]["RequestReference"]
                               for s in data["services"] if awaiting_repair(s)}
                waiting = [r for r in data["rows"] if r["reference"] in waiting_ids]
                incomplete = [r for r in data["rows"] if not r["compliant"]]
                waiting_tab, incomplete_tab = st.tabs([f"Réfection à réaliser ({len(waiting)})", f"Données à compléter ({len(incomplete)})"])
                with waiting_tab:
                    st.html(followup_html(waiting))
                with incomplete_tab:
                    st.html(followup_html(incomplete))
                    with st.expander("Motifs de non-conformité des données"):
                        for row in incomplete:
                            for error in row["conformity_errors"]:
                                st.text(error)
                st.caption("Aucune échéance contractuelle n’est renseignée dans le modèle actuel.")
            with photos_column, st.container(border=True):
                st.html('<h2 class="rp-section-title">Dernières photos terrain</h2>')
                render_recent_photos(data)
            with st.expander("Comprendre les indicateurs"):
                st.write("Les filtres sélectionnent les demandes selon leur commune et leur date de création. "
                         "Les interventions et prestations sont rattachées par leurs références. "
                         "Une intervention réalisée est une intervention clôturée avec une date de clôture dans la période. "
                         "Le délai mesure le nombre de jours entre la date de demande et la clôture de chaque intervention. "
                         "La conformité des données vérifie la demande et toutes ses interventions et prestations "
                         "avec les règles de validation des formulaires, dont CODEX-003. "
                         "Elle ne mesure pas la qualité physique des travaux. "
                         "Les demandes historiques peuvent nécessiter une requalification. "
                         "Les périodes sont glissantes jusqu’à aujourd’hui ; la dernière semaine comprend aujourd’hui et les six jours précédents.")
                if data["excluded_delays"]:
                    st.caption(f'{data["excluded_delays"]} délai(s) négatif(s) exclu(s) de la moyenne.')
        for tab, label, description in (
            (performance, "Performance", "Délais, suivi des interventions et indicateurs de qualité."),
            (dossiers, "Dossiers", "Analyse détaillée et suivi des dossiers du territoire."),
            (photos, "Photos", "Galerie des photos terrain et suivi visuel des travaux."),
            (export, "Export", "Exports des indicateurs et bilans de reporting."),
        ):
            with tab:
                st.html(f'<section class="rp-placeholder"><span>REPORTING COLLECTIVITÉ</span><h2>{label}</h2><p>{description}</p><p class="rp-footnote">Cet onglet sera construit lors d’une prochaine étape.</p></section>')
