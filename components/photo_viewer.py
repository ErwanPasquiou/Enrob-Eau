"""Visionneuse dans un onglet séparé, après authentification par app.py."""
import streamlit as st
from services import photo_service as photos
from services.access_service import PROFILS
from services.business_data_service import load_store, related_records


def render_photo_viewer():
    user = st.session_state.get("current_user")
    if not user or not user.get("actif") or user.get("profil") not in PROFILS:
        st.error("Accès impossible : utilisateur non autorisé.")
        return
    table = st.query_params.get("photo_table", "")
    reference = st.query_params.get("photo_parent", "")
    photo_id = st.query_params.get("photo", "")
    owner_email = str(user.get("email") or "") if st.query_params.get("photo_scope") == "mine" else None
    try:
        if user["profil"] == "agent externe" and table == "demandes":
            if not related_records(load_store(), reference)["prestations"]:
                raise ValueError("Cette demande n'est liée à aucune prestation accessible.")
        rows = photos.list_photos(table, reference, owner_email)
        row = next((r for r in rows if r["PhotoReference"] == photo_id), None)
        if row is None:
            raise ValueError("Cette photo n'existe plus ou n'appartient pas à ce dossier.")
        content = photos.read_photo(table, reference, photo_id, owner_email)
    except (ValueError, OSError) as exc:
        st.error(str(exc))
        return
    st.html("<style>.stApp {background: #f5f8fb !important;} .block-container {padding: 2rem !important; max-width: 1400px;} </style>")
    st.title(row["PhotoName"])
    st.caption("Vous pouvez fermer cet onglet pour revenir à votre demande.")
    st.download_button("Télécharger l'original", content, file_name=row["FileName"], mime=row["MimeType"])
    st.image(content, caption=row["Caption"] or None, use_column_width=True)
