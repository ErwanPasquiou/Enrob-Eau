"""Reporting collectivité calculé à partir des données métier de l'application."""
import streamlit as st

from components.header import render_header
from components.page_content import create_page_content
from components.reporting import kpi_html, render_charts, render_followup, render_recent_photos
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
        if data["undated_requests"]:
            st.caption(f'{data["undated_requests"]} demande(s) sans date dans cette collectivité sont exclues des indicateurs de période ; elles restent consultables dans Gestion des dossiers.')

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
                    render_followup(waiting, "reporting_waiting_page")
                with incomplete_tab:
                    render_followup(incomplete, "reporting_incomplete_page")
                    with st.expander("Motifs de non-conformité des données"):
                        st.dataframe([{"Demande": row["reference"], "Motif": error}
                                      for row in incomplete for error in row["conformity_errors"]],
                                     hide_index=True, use_container_width=True)
                st.caption("Aucune échéance contractuelle n’est renseignée dans le modèle actuel.")
            with photos_column, st.container(border=True):
                st.html('<h2 class="rp-section-title">Dernières photos terrain</h2>')
                render_recent_photos(data)
        for tab, label, description in (
            (performance, "Performance", "Délais, suivi des interventions et indicateurs de qualité."),
            (dossiers, "Dossiers", "Analyse détaillée et suivi des dossiers du territoire."),
            (photos, "Photos", "Galerie des photos terrain et suivi visuel des travaux."),
            (export, "Export", "Exports des indicateurs et bilans de reporting."),
        ):
            with tab:
                st.html(f'<section class="rp-placeholder"><span>REPORTING COLLECTIVITÉ</span><h2>{label}</h2><p>{description}</p><p class="rp-footnote">Cet onglet sera construit lors d’une prochaine étape.</p></section>')
