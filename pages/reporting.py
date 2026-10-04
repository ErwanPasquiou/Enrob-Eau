"""Espace de suivi des réfections définitives, accessible au sous-traitant."""
import pandas as pd
import streamlit as st

from components.header import render_header
from components.page_content import create_page_content
from components.dossier_forms import record_dialog
from components.photos import render_photos
from services.access_service import require_page
from services.business_data_service import load_store
from services.data_model import LABELS
from services.refection_service import prestation_rows, filter_prestations

user = require_page("refection")
render_header(active_page="Réfection définitive", initials=user.get("initials", ""),
              show_admin=user.get("profil") == "administrateur")
try:
    store = load_store()
except (OSError, ValueError) as exc:
    st.error(f"Impossible de charger les prestations : {exc}")
    st.stop()

with create_page_content():
    _, content, _ = st.columns([1, 24, 1], gap="small")
    with content:
        st.title("Réfection définitive")
        st.caption("Suivez les prestations, renseignez les travaux réalisés et ajoutez vos photos.")
        if st.session_state.get("dossier_notice"):
            st.success(st.session_state.pop("dossier_notice"))
            st.session_state.pop("dossier_saved_ref", None)
        rows = prestation_rows(store)
        search, city, status, repair = st.columns([2, 1, 1, 1])
        query = search.text_input("Rechercher une prestation", placeholder="Référence, intervention, adresse, motif…", key="refection_query")
        cities = city.multiselect("Communes", sorted({r["WorkCity"] for r in rows if r["WorkCity"]}), key="refection_cities")
        statuses = status.multiselect("Statuts", sorted({r["ServiceStatus"] for r in rows if r["ServiceStatus"]}), key="refection_statuses")
        repairs = repair.selectbox("Réfections définitives", ["Toutes", "À réaliser", "Réalisées"], key="refection_repair")
        filtered = filter_prestations(rows, query, cities, statuses, repairs)
        filtered.sort(key=lambda r: (bool(r["FinalRepairDate"]), r["BackfillDate"] or "", r["ServiceReference"]))
        st.subheader(f"Prestations ({len(filtered)})")
        if not filtered:
            st.info("Aucune prestation ne correspond aux filtres.")
        else:
            columns = ["ServiceReference", "WorkOrderReferenceSaur", "RequestReference", "WorkCity", "WorkAddress",
                       "WorkReason", "SurfaceRepairType", "ServiceStatus", "BackfillDate", "TemporaryRepairDate", "FinalRepairDate"]
            frame = pd.DataFrame(filtered, columns=columns)
            date_columns = ["BackfillDate", "TemporaryRepairDate", "FinalRepairDate"]
            for field in date_columns:
                frame[field] = pd.to_datetime(frame[field]).dt.date
            st.dataframe(frame.rename(columns=LABELS), hide_index=True, use_container_width=True,
                         column_config={LABELS[field]: st.column_config.DateColumn(format="DD/MM/YYYY") for field in date_columns})
            options = {r["ServiceReference"]: r for r in filtered}
            if st.session_state.get("refection_selected") not in options:
                st.session_state.refection_selected = next(iter(options))
            reference = st.selectbox("Prestation à consulter ou modifier", list(options), key="refection_selected",
                                     format_func=lambda ref: f"{ref} · {options[ref]['WorkCity']} · {options[ref]['WorkAddress']}")
            row = options[reference]
            original = next(r for r in store["prestations"] if r["ServiceReference"] == reference)
            with st.container(border=True):
                heading, action = st.columns([3, 1], vertical_alignment="center")
                heading.subheader(reference)
                heading.caption(f"Intervention {row['WorkOrderReferenceSaur']} · Demande {row['RequestReference']} · {row['ServiceStatus']}")
                if action.button("Modifier la prestation", key="refection_edit", use_container_width=True, type="primary"):
                    record_dialog("prestations", row["RequestReference"], original=original)
                st.write(f"{row['WorkAddress']} · {row['WorkCity']}")
                if row["Comment"]:
                    st.write(row["Comment"])
                service_photos, request_photos = st.tabs(["Photos de la prestation", "Photos de la demande · lecture seule"])
                with service_photos:
                    render_photos("prestations", reference)
                with request_photos:
                    st.caption("Photos du signalement initial, consultables sans modification.")
                    render_photos("demandes", row["RequestReference"], read_only=True)
