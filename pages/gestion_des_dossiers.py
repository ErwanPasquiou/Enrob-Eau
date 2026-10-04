from datetime import datetime
from html import escape
import pandas as pd
import streamlit as st

from components.header import render_header
from components.page_content import create_page_content
from components.styles import load_css
from services.business_data_service import load_store, filter_store, related_records, table_frame, export_csv
from services.data_model import SCHEMAS, LABELS, DATE_FIELDS
from components.dossier_forms import record_dialog, status_dialog, delete_dialog, create_service_dialog
from components.photos import render_photos
from services.dossier_edit_service import BLOCKED_REQUESTS

from services.access_service import require_page
user = require_page("dossiers")
render_header(active_page="Gestion des dossiers", initials=user.get("initials", ""), show_admin=user.get("profil") == "administrateur")
load_css("gestion_des_dossiers.css")
st.html('<span class="dossiers-page-marker"></span>')
try:
    store = load_store()
except (OSError, ValueError) as exc:
    st.error(f"Impossible de charger les dossiers : {exc}")
    st.stop()


def display_value(field, value):
    if value is None or value == "":
        return "Non renseigné"
    if isinstance(value, bool):
        return "Oui" if value else "Non"
    if field in DATE_FIELDS:
        parsed = datetime.fromisoformat(value)
        return parsed.strftime("%d/%m/%Y %H:%M" if "T" in value else "%d/%m/%Y")
    return str(value)


def properties(row, fields):
    if "WorkOrderReferenceEnrobEau" in fields:
        order = next(r for r in store["interventions"] if r["WorkOrderReferenceEnrobEau"] == row["WorkOrderReferenceEnrobEau"])
        row = dict(row, WorkOrderReferenceSaur=order["WorkOrderReferenceSaur"])
        fields = [f for f in fields if f != "WorkOrderReferenceEnrobEau"]
        if "WorkOrderReferenceSaur" not in fields:
            fields = [fields[0], "WorkOrderReferenceSaur", *fields[1:]]
    body = "".join(f'<tr><th>{escape(LABELS.get(field, field))}</th><td>{escape(display_value(field, row[field]))}</td></tr>' for field in fields)
    st.html(f'<table class="dossier-properties"><tbody>{body}</tbody></table>')


def linked_details(table, rows):
    if not rows:
        st.info("Aucun élément lié à cette demande.")
    for row in rows:
        title = row["WorkOrderReferenceSaur"] if table == "interventions" else row[SCHEMAS[table][0]]
        with st.expander(title, expanded=True):
            edit_col, delete_col = st.columns(2)
            if edit_col.button("Modifier", key=f"edit_{table}_{row[SCHEMAS[table][0]]}", use_container_width=True):
                record_dialog(table, st.session_state.dossier_selected, original=row)
            has_services = table == "interventions" and any(r["WorkOrderReferenceEnrobEau"] == row["WorkOrderReferenceEnrobEau"] for r in store["prestations"])
            if delete_col.button("Supprimer", key=f"delete_{table}_{row[SCHEMAS[table][0]]}", disabled=has_services, use_container_width=True,
                         help="Supprimez d'abord les prestations liées." if has_services else None):
                delete_dialog(table, row, st.session_state.dossier_selected)
            properties(row, SCHEMAS[table])
            if table == "prestations":
                render_photos(table, row["ServiceReference"])


def select_dossier(reference):
    st.session_state.dossier_selected = reference


def toggle_dossier_size():
    expanded = st.session_state.get("dossier_expanded", False)
    if not expanded:
        st.session_state.dossier_previous_view = {key: st.session_state.get(key) for key in (
            "dossier_query", "dossier_cities", "dossier_statuses", "dossier_period", "dossier_page")}
    else:
        st.session_state.dossier_restore_view = st.session_state.get("dossier_previous_view", {})
    st.session_state.dossier_expanded = not expanded


def progress_html(linked, compact=False, request_status=None):
    milestones = [
        ("Demande", True, "La demande existe."),
        ("Intervention", bool(linked["interventions"]), "Au moins une intervention est liée."),
        ("Prestation", bool(linked["prestations"]), "Au moins une prestation est liée."),
        ("Réfection provisoire", any(r["TemporaryRepairDate"] or r["HasTemporaryRepair"] or r["FinalRepairDate"] for r in linked["prestations"]), "Réfection provisoire ou définitive réalisée."),
        ("Réfection définitive", any(r["FinalRepairDate"] for r in linked["prestations"]), "Réfection définitive réalisée."),
        ("Clôture", request_status == "Clôturée", "La demande est clôturée."),
    ]
    stages = []
    for number, (label, done, rule) in enumerate(milestones, 1):
        refused = number == 1 and request_status == "Refusée"
        state = "Refusée" if refused else "Renseigné" if done else "À compléter"
        style = "refused" if refused else "done" if done else "pending"
        symbol = "✕" if refused else "✓" if done else number
        tooltip = escape(f"{label} : {state}. {rule}", quote=True)
        stages.append(
            f'<li class="dossier-stage {style}">'
            f'<span class="stage-dot {style}" tabindex="0" title="{tooltip}" aria-label="{tooltip}">'
            f'{symbol}</span><span class="stage-label">{label}</span></li>'
        )
    return '<ol class="dossier-progress' + (' compact' if compact else '') + '" aria-label="Avancement du dossier">' + ''.join(stages) + '</ol>'


with create_page_content():
    st.html('<div class="dossiers-content-start"></div>')
    st.title("Gestion des dossiers")
    restored_view = st.session_state.pop("dossier_restore_view", None)
    if restored_view:
        for key, value in restored_view.items():
            st.session_state[key] = value
    if st.session_state.get("dossier_notice"):
        st.success(st.session_state.pop("dossier_notice"))
    saved_ref = st.session_state.pop("dossier_saved_ref", None)
    if saved_ref:
        st.session_state.dossier_query = ""
        st.session_state.dossier_cities = []
        st.session_state.dossier_statuses = []
        st.session_state.dossier_period = ()
    expanded = st.session_state.get("dossier_expanded", False)
    if not expanded:
        if st.button("Nouvelle demande", type="primary"):
            record_dialog("demandes", None)
        search, city, status, dates = st.columns([2, 1, 1, 1.5])
        query = search.text_input("Rechercher", placeholder="Référence, commune, motif…", key="dossier_query")
        cities = city.multiselect("Communes", sorted({r["ReportedCity"] for r in store["demandes"] if r["ReportedCity"]}), placeholder="Toutes les communes", key="dossier_cities")
        statuses = status.multiselect("Statuts des demandes", sorted({r["RequestStatus"] for r in store["demandes"] if r["RequestStatus"]}), placeholder="Tous les statuts", key="dossier_statuses")
        # Reprendre la période avant de recréer le widget, sans double affectation.
        period_value = st.session_state.pop("dossier_period", ())
        period = dates.date_input("Période des demandes", value=period_value, format="DD/MM/YYYY", key="dossier_period")
        if len(period) == 1:
            st.caption("Sélectionnez la date de fin pour appliquer la période.")
        filtered = filter_store(store, query, cities, statuses, period)
        results = sorted(filtered["demandes"], key=lambda row: (row["RequestDate"] or "", row["RequestReference"]), reverse=True)
        listing, detail = st.columns([4, 6], gap="large")
        with listing:
            st.subheader(f"Dossiers ({len(results)})")
            signature = repr((query, cities, statuses, period))
            if st.session_state.get("dossier_signature") != signature:
                st.session_state.dossier_page = 1
                st.session_state.dossier_signature = signature
            count = max(1, (len(results) + 7) // 8)
            if saved_ref:
                for index, result in enumerate(results):
                    if result["RequestReference"] == saved_ref:
                        st.session_state.dossier_page = index // 8 + 1
                        st.session_state.dossier_selected = saved_ref
            st.session_state.dossier_page = min(st.session_state.get("dossier_page", 1), count)
            page = st.number_input("Page", min_value=1, max_value=count, key="dossier_page", step=1)
            visible = results[(page - 1) * 8:page * 8]
            refs = [r["RequestReference"] for r in visible]
            if st.session_state.get("dossier_selected") not in refs:
                st.session_state.dossier_selected = refs[0] if refs else None
            if not results:
                st.info("Aucun dossier ne correspond aux filtres.")
            for row in visible:
                ref = row["RequestReference"]
                st.button(f"{ref} · {row['RequestReason']}", key=f"gd_select_{ref}", use_container_width=True,
                          type="primary" if st.session_state.dossier_selected == ref else "secondary",
                          on_click=select_dossier, args=(ref,))
                st.caption(f"{row['ReportedCity']} · {row['ReportedAdress']} · {row['RequestStatus']}")
                st.html(progress_html(related_records(store, ref), compact=True, request_status=row["RequestStatus"]))

    else:
        results = store["demandes"]
        detail = st.container()
    with detail:
        if st.session_state.get("dossier_selected") or expanded:
            st.button("Quitter le grand écran" if expanded else "Afficher le dossier en grand", key="toggle_dossier_size", on_click=toggle_dossier_size)
        ref = st.session_state.get("dossier_selected")
        row = next((r for r in results if r["RequestReference"] == ref), None)
        if row is None:
            st.info("Aucun dossier sélectionné.")
        else:
            linked = related_records(store, ref)
            st.subheader(f"Dossier {ref}")
            st.write(row["RequestReason"])
            st.caption(f"{row['ReportedCity']} · {row['RequestStatus']}")
            edit, action, service_action = st.columns(3)
            if edit.button("Modifier la demande", use_container_width=True):
                record_dialog("demandes", ref, original=row)
            blocked = row["RequestStatus"] in BLOCKED_REQUESTS
            if action.button("Créer une intervention", type="primary", disabled=blocked, use_container_width=True):
                record_dialog("interventions", ref, parent=row)
            eligible_orders = [order for order in linked["interventions"] if order["WorkOrderStatus"] not in {"Clôturée", "En attente"}]
            if service_action.button("Créer une prestation", disabled=blocked or not eligible_orders, use_container_width=True,
                                     help="Une intervention active doit exister sur cette demande."):
                create_service_dialog(row, eligible_orders)
            if blocked:
                st.info("Reprenez le traitement de la demande pour créer de nouvelles interventions ou prestations.")
            elif not linked["interventions"]:
                st.info("Prochaine étape : créer l'intervention associée à cette demande.")
            elif not linked["prestations"]:
                st.info("Prochaine étape : cliquez sur Créer une prestation et choisissez l'intervention concernée.")
            with st.expander("Décision sur la demande"):
                targets = [("Démarrer / reprendre", "En cours"), ("Mettre en attente", "En attente"), ("Refuser la demande", "Refusée"), ("Clôturer la demande", "Clôturée")]
                for column, (label, target) in zip(st.columns(2) * 2, targets):
                    if column.button(label, key=f"decision_{target}", disabled=row["RequestStatus"] == target, use_container_width=True):
                        status_dialog(row, target)
            st.html(progress_html(linked, request_status=row["RequestStatus"]))
            st.caption("Vert : renseigné · Bleu : à compléter · Rouge : demande refusée · Une réfection définitive active les deux étapes.")
            general, request, orders, services = st.tabs(["Synthèse", "Demande", f"Interventions ({len(linked['interventions'])})", f"Prestations ({len(linked['prestations'])})"])
            with general:
                properties(row, ["RequestReference", "RequestDate", "RequestStatus", "RequestReason", "ReportedAdress", "ReportedCity", "CustomerName", "RequesterReference", "BusinessDomain", "EstimatedWorkDays", "RequestComment"])
                st.markdown("**Dates des travaux**")
                date_columns = ["ServiceReference", "ExcavationDate", "BackfillDate", "Concrete2CmDate", "TemporaryRepairDate", "FinalRepairDate"]
                st.dataframe(pd.DataFrame(linked["prestations"], columns=date_columns).rename(columns=LABELS), hide_index=True, use_container_width=True)
            with request:
                properties(row, SCHEMAS["demandes"])
                render_photos("demandes", ref)
            with orders:
                linked_details("interventions", linked["interventions"])
            with services:
                linked_details("prestations", linked["prestations"])
            st.caption("Exporter ce dossier :")
            dossier_store = {"demandes": [row], **linked}
            for column, table in zip(st.columns(3), SCHEMAS):
                with column:
                    st.html('<span class="dossier-export-marker"></span>')
                    st.download_button(f"CSV {table}", export_csv(table_frame(dossier_store, table)), file_name=f"{ref}_{table}.csv", mime="text/csv", key=f"dossier_export_{table}", use_container_width=True)
