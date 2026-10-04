import streamlit as st
from components.header import render_header
from components.page_content import create_page_content
from services.business_data_service import load_store, filter_store, table_frame, export_csv
from services.data_model import SCHEMAS, LABELS

from services.access_service import require_page
user = require_page("export")
render_header(active_page="Export", initials=user.get("initials", ""), show_admin=user.get("profil") == "administrateur")
with create_page_content():
    st.title("Export")
    st.caption("Données d'exemple · Un fichier CSV par table, avec les noms de colonnes du modèle.")
    try:
        store = load_store()
    except (OSError, ValueError) as exc:
        st.error(f"Impossible de charger les données : {exc}")
        st.stop()
    tables = st.multiselect("Tables à extraire", list(SCHEMAS), default=list(SCHEMAS), format_func=str.capitalize)
    search, city, status, dates = st.columns(4)
    query = search.text_input("Recherche dans les dossiers et leurs éléments liés")
    cities = city.multiselect("Communes des demandes", sorted({r["ReportedCity"] for r in store["demandes"] if r["ReportedCity"]}))
    statuses = status.multiselect("Statuts des demandes", sorted({r["RequestStatus"] for r in store["demandes"] if r["RequestStatus"]}))
    period = dates.date_input("Période des demandes", value=(), format="DD/MM/YYYY")
    st.caption("Les filtres sélectionnent les demandes et toutes leurs interventions et prestations liées.")
    if len(period) == 1:
        st.info("Sélectionnez la date de fin pour appliquer la période.")
    filtered = filter_store(store, query, cities, statuses, period)
    if not tables:
        st.info("Sélectionnez au moins une table.")
    for table in tables:
        with st.expander(table.capitalize(), expanded=True):
            columns = st.multiselect("Colonnes à conserver", SCHEMAS[table], default=SCHEMAS[table],
                                    format_func=lambda f: f"{LABELS.get(f, f)} ({f})", key=f"export_columns_{table}")
            if not columns:
                st.info("Sélectionnez au moins une colonne pour exporter cette table.")
                continue
            frame = table_frame(filtered, table, columns)
            st.caption(f"{len(frame)} ligne(s) à exporter · aperçu des {min(len(frame), 1000)} premières lignes.")
            st.dataframe(frame.head(1000), hide_index=True, use_container_width=True)
            st.download_button(f"Télécharger {table}.csv", export_csv(frame), file_name=f"{table}.csv",
                               mime="text/csv", key=f"export_download_{table}", disabled=frame.empty)
    st.caption("L'export contient toutes les lignes filtrées, même au-delà des 1 000 lignes de l'aperçu. Séparateur : point-virgule ; encodage : UTF-8 avec BOM.")
