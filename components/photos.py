"""Sélection cumulative des photos et accès à une visionneuse séparée."""
from urllib.parse import urlencode
from uuid import uuid4
import streamlit as st
from services import photo_service as photos


def append_uploads(queue, uploads):
    if len(queue) + len(uploads) > photos.MAX_BATCH:
        raise ValueError("Ajoutez au maximum 20 photos à la fois.")
    additions = []
    for upload in uploads:
        photo = photos.prepare_photo(upload.name, upload.getvalue(), photo_name=upload.name)
        photo.update(DraftId=uuid4().hex, PhotoName="")
        additions.append(photo)
    queue.extend(additions)


def clear_uploads(prefix):
    for key in list(st.session_state):
        if key.startswith(f"{prefix}_"):
            del st.session_state[key]


def refresh_uploads(prefix, scope="app"):
    # Attendre que les autres champs aient été rendus avant de relancer la page.
    if st.session_state.pop(f"{prefix}_refresh", False):
        st.rerun(scope=scope)


def remove_upload(prefix, draft_id):
    queue = st.session_state[f"{prefix}_queue"]
    queue[:] = [photo for photo in queue if photo["DraftId"] != draft_id]


def render_upload_editor(prefix):
    queue = st.session_state.setdefault(f"{prefix}_queue", [])
    revision_key = f"{prefix}_revision"
    revision = st.session_state.get(revision_key, 0)
    st.caption("Prenez plusieurs photos à la suite ou sélectionnez plusieurs fichiers. Jusqu'à 20 photos, 15 Mo chacune.")
    source = st.radio("Source des photos", ["Document / galerie", "Appareil photo"], index=None,
                      key=f"{prefix}_source", horizontal=True)
    uploads = []
    if source == "Appareil photo":
        capture = st.camera_input("Prendre une photo", key=f"{prefix}_camera_{revision}", disabled=len(queue) >= photos.MAX_BATCH)
        uploads = [capture] if capture else []
    elif source == "Document / galerie":
        uploads = st.file_uploader("Ajouter des photos", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True,
                                   key=f"{prefix}_uploads_{revision}", disabled=len(queue) >= photos.MAX_BATCH) or []
    if uploads:
        try:
            append_uploads(queue, uploads)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.session_state[revision_key] = revision + 1
            st.session_state[f"{prefix}_refresh"] = True
    if queue:
        st.markdown(f"**{len(queue)} photo(s) à enregistrer**")
        st.caption("Chaque photo doit avoir un nom. Vous pouvez continuer à en ajouter ci-dessus.")
    for photo in list(queue):
        key = f"{prefix}_{photo['DraftId']}"
        with st.container(border=True):
            preview, fields = st.columns([1, 3])
            preview.image(photo["Content"], width=110)
            photo["PhotoName"] = fields.text_input("Nom de la photo *", value=photo["PhotoName"],
                                                   placeholder="Ex. Vue d'ensemble avant travaux", key=f"{key}_name")
            fields.caption(photo["FileName"])
            fields.button("Retirer", key=f"{key}_remove", on_click=remove_upload, args=(prefix, photo["DraftId"]))
    if st.button("Terminer", key=f"{prefix}_done", type="primary"):
        if any(not photo["PhotoName"].strip() for photo in queue):
            st.error("Donnez un nom à chaque photo avant de terminer.")
        else:
            return True
    return False


@st.dialog("Ajouter une photo", width="large")
def photo_dialog(prefix):
    if render_upload_editor(prefix):
        st.rerun()
    refresh_uploads(prefix, scope="fragment")


def photo_uploads(prefix, in_dialog=False):
    queue = st.session_state.setdefault(f"{prefix}_queue", [])
    if st.button("Ajouter une photo", key=f"{prefix}_open"):
        if in_dialog:
            st.session_state[f"{prefix}_editor"] = True
            st.session_state[f"{prefix}_refresh"] = True
        else:
            photo_dialog(prefix)
    if queue:
        st.caption(f"{len(queue)} photo(s) sélectionnée(s) · " + ", ".join(p["PhotoName"] or "Nom à renseigner" for p in queue))
    return queue


def prepare_uploads(uploads):
    if len(uploads) > photos.MAX_BATCH:
        raise ValueError("Ajoutez au maximum 20 photos à la fois.")
    return [photos.prepare_photo(p["FileName"], p["Content"], p.get("Caption", ""), p.get("PhotoName")) for p in uploads]


def photo_url(table, reference, photo_id, own=False):
    return "?" + urlencode({"photo": photo_id, "photo_table": table, "photo_parent": reference,
                            "photo_scope": "mine" if own else "dossiers"})


def render_photos(table, reference, owner_email=None, read_only=False):
    # Une ancienne sélection de modification ne doit jamais contourner la lecture seule.
    read_only = read_only or (table == "demandes" and st.session_state.get("current_user", {}).get("profil") == "agent externe")
    prefix = f"photos_{table}_{reference}"
    st.markdown("### Photos")
    try:
        rows = photos.list_photos(table, reference, owner_email)
        if not rows:
            st.caption("Aucune photo pour le moment.")
        for row in rows:
            pid = row["PhotoReference"]
            key = f"{prefix}_{pid}_{row['Version']}"
            with st.container(border=True):
                columns = st.columns([3, 1] if read_only else [3, 1, 1, 1])
                title, open_col = columns[:2]
                title.write(row["PhotoName"])
                title.caption(f"{row['SizeBytes'] / 1024:.0f} Ko · {row['CreatedAt'][:10]}")
                if row["Caption"]:
                    title.caption(row["Caption"])
                open_col.link_button("Ouvrir ↗", photo_url(table, reference, pid, owner_email is not None),
                                     help="Ouvrir la photo dans un nouvel onglet", use_container_width=True)
                if read_only:
                    continue
                edit_col, delete_col = columns[2:]
                if edit_col.button("Modifier", key=f"{key}_edit", use_container_width=True):
                    st.session_state[f"{prefix}_edit"] = pid
                if delete_col.button("Supprimer", key=f"{key}_delete", use_container_width=True):
                    st.session_state[f"{prefix}_delete"] = pid
                if st.session_state.get(f"{prefix}_edit") == pid:
                    with st.form(f"{key}_form"):
                        name = st.text_input("Nom de la photo *", value=row["PhotoName"])
                        caption = st.text_input("Légende", value=row["Caption"])
                        replacement = st.file_uploader("Remplacer le fichier (facultatif)", type=["jpg", "jpeg", "png", "webp"])
                        save, cancel = st.columns(2)
                        submitted = save.form_submit_button("Enregistrer")
                        cancelled = cancel.form_submit_button("Annuler")
                    if cancelled:
                        st.session_state.pop(f"{prefix}_edit", None)
                        st.rerun()
                    if submitted:
                        replacement_data = {"FileName": replacement.name, "Content": replacement.getvalue()} if replacement else None
                        photos.update_photo(table, reference, row, caption, replacement_data, owner_email, photo_name=name)
                        st.session_state.pop(f"{prefix}_edit", None)
                        st.rerun()
                if st.session_state.get(f"{prefix}_delete") == pid:
                    st.warning(f"Supprimer la photo « {row['PhotoName']} » ?")
                    confirm, cancel = st.columns(2)
                    if confirm.button("Confirmer la suppression", key=f"{key}_confirm"):
                        photos.delete_photo(table, reference, row, owner_email)
                        st.session_state.pop(f"{prefix}_delete", None)
                        st.rerun()
                    if cancel.button("Annuler", key=f"{key}_cancel_delete"):
                        st.session_state.pop(f"{prefix}_delete", None)
                        st.rerun()
        if read_only:
            return
        uploads = photo_uploads(f"{prefix}_add")
        if uploads:
            if st.button(f"Enregistrer les photos ({len(uploads)})", key=f"{prefix}_save", disabled=not uploads, type="primary"):
                photos.add_photos(table, reference, prepare_uploads(uploads),
                                  st.session_state.get("current_user", {}).get("email", ""), owner_email)
                clear_uploads(f"{prefix}_add")
                st.rerun()
        refresh_uploads(f"{prefix}_add")
    except (ValueError, OSError) as exc:
        st.error(str(exc))
