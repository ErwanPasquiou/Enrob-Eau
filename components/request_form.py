"""Les cinq sections du formulaire Demande, communes aux deux parcours."""
from datetime import datetime

import streamlit as st

from components.address_fields import address_fields
from services.data_model import LABELS
from services.request_model import REQUEST_CHOICES, MULTIPLE_FIELDS, display_choices


REQUEST_GROUPS = [
    ("Localisation des travaux", "AffectedStreets"),
    ("Informations sur la demande", "RequestDate RequesterReference CustomerName BusinessDomain LeakReportReference RequestReason MeterReference"),
    ("Caractéristiques des travaux", "ReportedMaterial ReportedDiameter ReportedRoadType ReportedSurfaceType EstimatedWorkDays"),
    ("Contraintes et préparation du chantier", "DictAtuIndicator WaterShutdownIndicator RoadImpact SafetyInstructions SpecialConditions"),
    ("Commentaire complémentaire", "RequestComment"),
]


def render_request_fields(row, prefix, *, mobile, creating):
    selected_address = None
    other_memory = f"request_other_{prefix}"
    other_key = f"{prefix}_ReportedRoadTypeOther"
    st.session_state.setdefault(other_memory, row["ReportedRoadTypeOther"])
    for title, fields in REQUEST_GROUPS:
        with st.container(border=True):
            st.markdown(f"**{title}**")
            if title == "Localisation des travaux":
                selected_address = address_fields(row, prefix)
                if selected_address:
                    row.update(selected_address)
            for field in fields.split():
                key = f"{prefix}_{field}"
                label, value = LABELS[field], row[field]
                if field in REQUEST_CHOICES:
                    options = REQUEST_CHOICES[field]
                    if field in MULTIPLE_FIELDS:
                        previous = value if isinstance(value, list) else []
                        defaults = [v for v in previous if v in options]
                        legacy = value is not None and (not isinstance(value, list) or any(v not in options for v in previous))
                        row[field] = st.multiselect(label + " *", options, default=defaults, key=key)
                    else:
                        legacy = value is not None and value not in options
                        row[field] = st.selectbox(label + " *", options,
                                                   index=options.index(value) if value in options else None,
                                                   placeholder="Choisir une valeur", key=key)
                    if legacy:
                        st.caption(f"Valeur historique à requalifier pour « {label} » : {display_choices(value)}. Choisissez une valeur de la liste avant d'enregistrer.")
                    if field == "ReportedRoadType" and "Autre" in row[field]:
                        row["ReportedRoadTypeOther"] = st.text_input(
                            LABELS["ReportedRoadTypeOther"] + " *", value=st.session_state[other_memory] or "",
                            key=other_key)
                    elif field == "ReportedRoadType":
                        if other_key in st.session_state:
                            st.session_state[other_memory] = st.session_state[other_key]
                        row["ReportedRoadTypeOther"] = st.session_state[other_memory]
                elif field == "MeterReference":
                    required = row["RequestReason"] == "Renouvellement de branchement"
                    row[field] = st.text_input(label, value=value or "", key=key,
                                               help="Obligatoire pour le motif Renouvellement de branchement ; facultatif sinon.")
                    if required:
                        st.caption("Matricule Compteur obligatoire pour un renouvellement de branchement.")
                elif field == "RequesterReference":
                    row[field] = st.text_input(label, value=value or "", key=key,
                                               disabled=mobile or (creating and bool(value)), placeholder="prenom.nom@entreprise.fr")
                elif field == "RequestDate":
                    selected = st.date_input(label, value=datetime.fromisoformat(value).date() if value else None,
                                             format="DD/MM/YYYY", key=key)
                    row[field] = selected.isoformat() if selected else None
                elif field in {"ReportedDiameter", "EstimatedWorkDays"}:
                    row[field] = st.number_input(label, min_value=0.0, value=float(value) if value is not None else None,
                                                 step=1.0, key=key, placeholder="Non renseigné")
                elif field in {"RequestComment", "SafetyInstructions", "SpecialConditions"}:
                    row[field] = st.text_area(label, value=value or "", key=key, placeholder="Saisissez un commentaire…")
                else:
                    row[field] = st.text_input(label, value=value or "", key=key, placeholder="À renseigner")
    return selected_address
