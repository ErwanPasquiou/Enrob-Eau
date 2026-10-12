"""Reporting collectivité : première itération, vue d'ensemble fictive."""
import streamlit as st

from components.header import render_header
from components.page_content import create_page_content
from components.reporting import kpi_html, charts_html, priorities_html, photos_html
from components.styles import load_css
from services.access_service import require_page
from services.reporting_demo_service import CITIES, PERIODS, snapshot, priority_rows

user = require_page("reporting")
load_css("reporting.css")
render_header(active_page="Reporting", initials=user.get("initials", ""),
              show_admin=user.get("profil") == "administrateur")

with create_page_content():
    _, content, _ = st.columns([.5, 24, .5], gap="small")
    with content:
        st.html('<div class="reporting-root"></div>')
        title, city_column, period_column = st.columns([3.6, 1.2, 1], vertical_alignment="center")
        with title:
            st.html('<div class="rp-heading"><h1>Reporting collectivité</h1><p>Pilotez l’activité Enrob’Eau sur votre territoire grâce à des indicateurs consolidés.</p></div>')
        city = city_column.selectbox("Collectivité", ["Toutes les communes", *CITIES], key="reporting_city")
        period = period_column.selectbox("Période", list(PERIODS), key="reporting_period")
        data = snapshot(city, period)
        st.html(f'<p class="rp-demo">Données fictives · situation au {data["end"]:%d/%m/%Y} · demandes du {data["start"]:%d/%m/%Y} au {data["end"]:%d/%m/%Y}</p>')

        overview, performance, dossiers, photos, export = st.tabs(["Vue d’ensemble", "Performance", "Dossiers", "Photos", "Export"])
        with overview:
            st.html(kpi_html(data))
            st.html(charts_html(data))
            priority_column, photos_column = st.columns([2.18, 1], gap="small")
            with priority_column, st.container(border=True):
                st.html('<h2 class="rp-section-title">Dossiers prioritaires</h2>')
                late = priority_rows(data["rows"])
                soon = priority_rows(data["rows"], upcoming=True)
                late_tab, soon_tab = st.tabs([f"En retard ({len(late)})", f"Prochaines échéances ({len(soon)})"])
                with late_tab:
                    st.html(priorities_html(late))
                with soon_tab:
                    st.html(priorities_html(soon, upcoming=True))
            with photos_column, st.container(border=True):
                st.html('<h2 class="rp-section-title">Dernières photos terrain</h2>')
                st.html(photos_html(data["rows"]))
            with st.expander("Comprendre les indicateurs de démonstration"):
                st.write("Les filtres sélectionnent les demandes selon leur commune et leur date de création. "
                         "Tous les blocs portent sur cette même sélection. Le mois en cours est partiel. "
                         "Les interventions et réfections sont comptées à leur date de réalisation. "
                         "Le délai correspond à la moyenne des durées entre création et intervention réalisée. "
                         "La conformité est un attribut fictif du scénario ; sa définition métier reste à valider. "
                         "Les échéances à venir couvrent les 14 jours suivant la date de démonstration. "
                         "Ces données sont indépendantes des demandes enregistrées dans l’application.")
        for tab, label, description in (
            (performance, "Performance", "Délais, suivi des interventions et indicateurs de qualité."),
            (dossiers, "Dossiers", "Analyse détaillée et suivi des dossiers du territoire."),
            (photos, "Photos", "Galerie des photos terrain et suivi visuel des travaux."),
            (export, "Export", "Exports des indicateurs et bilans de reporting."),
        ):
            with tab:
                st.html(f'<section class="rp-placeholder"><span>REPORTING COLLECTIVITÉ</span><h2>{label}</h2><p>{description}</p><p class="rp-footnote">Cet onglet sera construit lors d’une prochaine étape.</p></section>')
