"""Formulaires contextuels des dossiers."""
from copy import deepcopy
from datetime import datetime, time
import streamlit as st

from services.data_model import SCHEMAS, LABELS, DATE_FIELDS, BOOL_FIELDS
from services.business_data_service import load_store
from services.dossier_edit_service import new_record, save_record, change_request_status, delete_record, STATUSES
from components.photos import photo_uploads, prepare_uploads, clear_uploads, refresh_uploads, render_upload_editor
from components.request_form import render_request_fields, REQUEST_GROUPS
from services.request_model import adapt_request, display_choices

GROUPS = {
    "demandes": REQUEST_GROUPS,
    "interventions": [
        ("Intervention · référence SI SAUR", "WorkOrderReferenceSaur ClosedAt WorkOrderStatus SaurComment"),
        ("Suivi de la DICT / de l'ATU", "IssuedAt ReceivedAt"),
        ("Information de la commune", "CityInformedAt CityWorksComment"),
        ("Information des abonnés", "CustomerInformedAt CustomerWorksComment"),
    ],
    "prestations": [
        ("Travaux", "ServiceStatus ServiceCode WorkAddress WorkCity WorkCoordinates WorkReason SurfaceRepairType RoadType Comment"),
        ("Avancement et dates", "ExcavationDate BackfillDate HasConcrete2Cm Concrete2CmDate HasTemporaryRepair TemporaryRepairDate FinalRepairDate"),
    ],
}


def completed(reference, message):
    st.session_state.dossier_saved_ref = reference
    st.session_state.dossier_notice = message
    st.rerun()


@st.dialog("Modifier le statut de la demande", width="large")
def status_dialog(original, target):
    st.write(f"**{original['RequestReference']} · {original['RequestStatus']} → {target}**")
    st.caption("Cette décision concerne la demande. Les interventions et prestations existantes sont conservées.")
    with st.form("request_status_form"):
        reason = st.text_area("Motif de la décision", placeholder="Précisez le motif…")
        left, right = st.columns(2)
        submit = left.form_submit_button("Confirmer", type="primary", use_container_width=True)
        cancel = right.form_submit_button("Annuler", use_container_width=True)
    if cancel:
        st.rerun()
    if submit:
        try:
            change_request_status(original, target, reason)
        except (ValueError, OSError) as exc:
            st.error(str(exc))
        else:
            completed(original["RequestReference"], f"Demande passée au statut « {target} ».")


def render_record_form(table, request_ref, original=None, parent=None, request=None, mobile=False, in_dialog=False):
    if st.session_state.get("current_user", {}).get("profil") == "agent externe" and (table != "prestations" or original is None):
        st.error("Ce profil peut uniquement modifier les prestations existantes.")
        return
    draft_key = f"draft_{table}_{request_ref}_{parent.get(SCHEMAS['interventions'][0], '') if parent else ''}_{'mobile' if mobile else 'dialog'}"
    if original is None and draft_key not in st.session_state:
        try:
            st.session_state[draft_key] = new_record(table, parent)
        except (ValueError, OSError) as exc:
            st.error(f"Impossible de préparer la fiche : {exc}")
            return
    row = deepcopy(original) if original is not None else deepcopy(st.session_state[draft_key])
    if table == "demandes":
        row = adapt_request(row)
    prefix = row[SCHEMAS[table][0]] or f"new_intervention_{request_ref or row.get('RequestReference')}"
    if table == "demandes" and original is None:
        row["RequesterReference"] = st.session_state.get("current_user", {}).get("email", "")
    if original is None and table == "prestations" and request:
        row.update(WorkAddress=request["ReportedAdress"], WorkCity=request["ReportedCity"],
                   WorkCoordinates=request.get("LocationLandmark"),
                   WorkReason=request["RequestReason"], RoadType=display_choices(request["ReportedRoadType"]),
                   SurfaceRepairType=display_choices(request["ReportedSurfaceType"]))
    values_key = f"record_values_{prefix}"
    row = deepcopy(st.session_state.get(values_key, row))
    photo_prefix = f"{prefix}_new_photos"
    if in_dialog and st.session_state.get(f"{photo_prefix}_editor"):
        st.subheader("Ajouter une photo")
        if render_upload_editor(photo_prefix):
            st.session_state[f"{photo_prefix}_editor"] = False
            st.rerun(scope="fragment")
        refresh_uploads(photo_prefix, scope="fragment")
        return
    singular = {"demandes": "demande", "interventions": "intervention", "prestations": "prestation"}[table]
    st.subheader(f"{'Modifier la' if original else 'Créer une'} {singular}")
    if table != "interventions":
        st.caption(f"Référence : {row[SCHEMAS[table][0]]}")
    if table == "interventions":
        st.info(f"{LABELS['RequestReference']} : {row['RequestReference']}")
    elif table == "prestations":
        order = parent
        if order is None:
            order = next((r for r in load_store()["interventions"]
                          if r["WorkOrderReferenceEnrobEau"] == row["WorkOrderReferenceEnrobEau"]), None)
        if order:
            st.info(f"{LABELS['WorkOrderReferenceSaur']} : {order['WorkOrderReferenceSaur']}")
    selected_address = None
    uploads = []
    if original is None and table in {"demandes", "prestations"}:
        st.markdown("**Photos (facultatif)**")
        uploads = photo_uploads(photo_prefix, in_dialog=in_dialog)
    with st.container():
        if table == "demandes":
            selected_address = render_request_fields(row, prefix, mobile=mobile, creating=original is None)
        for title, fields in (GROUPS[table] if table != "demandes" else []):
            st.markdown(f"**{title}**")
            left, right = tuple(st.columns(2)) if not mobile else (st.container(), None)
            if mobile:
                right = left
            for index, field in enumerate(fields.split()):
                if table == "demandes" and field in {"ReportedAdress", "ReportedCity", "LocationLandmark"}:
                    continue
                with (left if index % 2 == 0 else right):
                    label, value = LABELS[field], row[field]
                    if field == "WorkOrderReferenceSaur" and table == "interventions":
                        row[field] = st.text_input("Référence de l'intervention SI SAUR *", value=value or "", key=f"{prefix}_{field}",
                                                   placeholder="Référence issue du SI SAUR")
                    elif field == "WorkOrderStatus" and row["ClosedAt"]:
                        row[field] = "Clôturée"
                        st.text_input(label, value="Clôturée", disabled=True, key=f"{prefix}_{field}_auto")
                    elif field == "RequesterReference":
                        row[field] = st.text_input(label, value=value or "", key=f"{prefix}_{field}",
                                                   disabled=mobile or (original is None and bool(value)), placeholder="prenom.nom@entreprise.fr")
                    elif field in STATUSES:
                        options = [v for v in STATUSES[field] if field != "WorkOrderStatus" or v != "Clôturée"]
                        if field == "WorkOrderStatus" and value == "Clôturée":
                            value = "En cours"
                        row[field] = st.selectbox(label, options, index=options.index(value) if value in options else 0, key=f"{prefix}_{field}")
                    elif field in DATE_FIELDS:
                        flag = {"Concrete2CmDate": "HasConcrete2Cm", "TemporaryRepairDate": "HasTemporaryRepair"}.get(field)
                        if flag and row[flag] is True:
                            row[field] = row["BackfillDate"]
                            st.text_input(label, value=row[field] or "Renseignez la date de remblaiement", disabled=True, key=f"{prefix}_{field}_auto")
                            continue
                        parsed = datetime.fromisoformat(value) if value else None
                        selected = st.date_input(label, value=parsed.date() if parsed else None, format="DD/MM/YYYY", key=f"{prefix}_{field}")
                        if field.endswith("At"):
                            row[field] = datetime.combine(selected, time(0)).isoformat() if selected else None
                        else:
                            row[field] = selected.isoformat() if selected else None
                    elif field in BOOL_FIELDS:
                        choice = st.selectbox(label, [None, True, False], index=[None, True, False].index(value),
                                              format_func=lambda v: "Non renseigné" if v is None else "Oui" if v else "Non", key=f"{prefix}_{field}")
                        row[field] = choice
                    elif field in {"ReportedDiameter", "EstimatedWorkDays"}:
                        row[field] = st.number_input(label, min_value=0.0, value=float(value) if value is not None else None, step=1.0, key=f"{prefix}_{field}", placeholder="Non renseigné")
                    elif "Comment" in field or field in {"SafetyInstructions", "SpecialConditions"}:
                        row[field] = st.text_area(label, value=value or "", key=f"{prefix}_{field}", placeholder="Saisissez un commentaire…")
                    else:
                        row[field] = st.text_input(label, value=str(value) if value is not None else "", key=f"{prefix}_{field}", placeholder="À renseigner")
        if table == "interventions":
            st.caption("La date de clôture passe automatiquement l'intervention à Clôturée. Elle se clôture aussi lorsque toutes ses prestations sont terminées. Les dates sont enregistrées à 00:00.")
        if table == "prestations":
            st.caption("Oui : date du remblaiement. Non : date à saisir manuellement. Une prestation terminée nécessite une date de réfection définitive.")
        left, right = st.columns(2)
        submit_button = left.button
        cancel_button = right.button
        submit = submit_button("Enregistrer les modifications" if original else f"Créer la {singular}", type="primary", use_container_width=True)
        cancel = cancel_button("Annuler", use_container_width=True)
    if in_dialog and st.session_state.get(f"{photo_prefix}_editor"):
        st.session_state[values_key] = deepcopy(row)
        if table == "demandes":
            st.session_state[f"request_other_{prefix}"] = row["ReportedRoadTypeOther"]
            for field in ("AffectedStreets", "MeterReference"):
                st.session_state[f"request_hidden_{prefix}_{field}"] = row[field]
    refresh_uploads(photo_prefix, scope="fragment" if in_dialog else "app")
    if cancel:
        st.session_state.pop(values_key, None)
        st.session_state.pop(f"request_other_{prefix}", None)
        for field in ("AffectedStreets", "MeterReference"):
            st.session_state.pop(f"request_hidden_{prefix}_{field}", None)
        if mobile:
            st.session_state.forms_new = False
            st.session_state.forms_edit = False
        st.rerun()
    if submit:
        try:
            if table == "demandes" and selected_address is None:
                raise ValueError("Sélectionnez une adresse ou utilisez la saisie libre.")
            if table == "demandes" and original is None:
                row["RequesterReference"] = st.session_state.get("current_user", {}).get("email", "")
            prepared = prepare_uploads(uploads)
            email = st.session_state.get("current_user", {}).get("email", "")
            save_record(table, row, original, photos=prepared, actor=email, owner_email=email if mobile else None)
        except (ValueError, OSError) as exc:
            st.error(str(exc))
        else:
            clear_uploads(f"{prefix}_new_photos")
            st.session_state.pop(values_key, None)
            st.session_state.pop(f"request_other_{prefix}", None)
            for field in ("AffectedStreets", "MeterReference"):
                st.session_state.pop(f"request_hidden_{prefix}_{field}", None)
            st.session_state.pop(draft_key, None)
            if mobile:
                st.session_state.forms_new = False
                st.session_state.forms_edit = False
                st.session_state.forms_selected = row["RequestReference"]
                st.session_state.forms_saved = row["RequestReference"]
                st.rerun()
            completed(request_ref or row["RequestReference"], f"{singular.capitalize()} {'modifiée' if original else 'créée'} et enregistrée.")


@st.dialog("Fiche du dossier", width="large")
def record_dialog(table, request_ref, original=None, parent=None, request=None):
    render_record_form(table, request_ref, original, parent, request, in_dialog=True)


@st.dialog("Créer une prestation", width="large")
def create_service_dialog(request, interventions):
    options = {row["WorkOrderReferenceEnrobEau"]: row for row in interventions}
    reference = st.selectbox("Intervention concernée *", list(options), key=f"service_parent_{request['RequestReference']}",
                             format_func=lambda ref: options[ref]["WorkOrderReferenceSaur"])
    if reference:
        render_record_form("prestations", request["RequestReference"], parent=options[reference], request=request, in_dialog=True)


@st.dialog("Confirmer la suppression", width="large")
def delete_dialog(table, original, request_ref):
    reference = original["WorkOrderReferenceSaur"] if table == "interventions" else original[SCHEMAS[table][0]]
    st.warning(f"Supprimer définitivement {reference} ?")
    if table == "interventions":
        st.caption("La suppression est possible uniquement si aucune prestation n'est liée à cette intervention.")
    left, right = st.columns(2)
    if left.button("Confirmer la suppression", type="primary", use_container_width=True):
        try:
            delete_record(table, original)
        except (ValueError, OSError) as exc:
            st.error(str(exc))
        else:
            completed(request_ref, f"{reference} supprimée.")
    if right.button("Annuler", use_container_width=True):
        st.rerun()
