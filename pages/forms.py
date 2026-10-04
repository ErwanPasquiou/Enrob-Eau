import streamlit as st
from components.header import render_header
from components.page_content import create_page_content
from components.styles import load_css
from components.dossier_forms import render_record_form
from services.business_data_service import load_store
from components.request_details import render_request_details
from components.photos import render_photos
from components.request_list import render_request_summary

from services.access_service import require_page
user = require_page("forms")
render_header(active_page="Demandes", initials=user.get("initials", ""), show_admin=user.get("profil") == "administrateur")
load_css("forms.css")
st.html('<span class="request-form-page"></span>')


def open_request(reference):
    st.session_state.forms_selected = reference
    st.session_state.forms_edit = False
    st.session_state.forms_new = False


def return_to_list():
    st.session_state.forms_selected = None
    st.session_state.forms_edit = False


with create_page_content():
    heading, new_action = st.columns([4, 1], vertical_alignment="center")
    with heading:
        st.title("Mes demandes")
        st.caption("Retrouvez vos signalements et suivez leur traitement.")
    if st.session_state.get("forms_saved"):
        st.success(f"Demande {st.session_state.pop('forms_saved')} enregistrée.")
    if st.session_state.get("forms_new"):
        render_record_form("demandes", None, mobile=True)
    else:
        if new_action.button("Nouveau", type="primary", use_container_width=True):
            st.session_state.forms_new = True
            st.session_state.forms_edit = False
            st.rerun()
        try:
            email = str(user.get("email") or "").strip().casefold()
            rows = [r for r in load_store()["demandes"] if email and str(r.get("RequesterReference") or "").strip().casefold() == email]
        except (OSError, ValueError) as exc:
            st.error(f"Impossible de charger les demandes : {exc}")
            st.stop()
        if rows:
            rows.sort(key=lambda r: r["RequestDate"] or "", reverse=True)
            selected = next((r for r in rows if r["RequestReference"] == st.session_state.get("forms_selected")), None)
            if selected:
                st.button("← Retour à mes demandes", on_click=return_to_list, key="forms_back")
                with st.container(border=True):
                    render_request_summary(selected)
                if st.session_state.get("forms_edit"):
                    render_record_form("demandes", selected["RequestReference"], original=st.session_state.forms_edit_original, mobile=True)
                else:
                    if st.button("Modifier ma demande", key="forms_modify"):
                        st.session_state.forms_edit = True
                        st.session_state.forms_edit_original = selected.copy()
                        st.rerun()
                    render_request_details(selected)
                    render_photos("demandes", selected["RequestReference"], owner_email=email)
            else:
                search, status = st.columns([3, 1])
                query = search.text_input("Rechercher une demande", placeholder="Référence, motif, adresse ou commune…", key="forms_search")
                chosen_status = status.selectbox("Statut", ["Tous les statuts", *sorted({r["RequestStatus"] for r in rows})], key="forms_filter_status")
                visible = [r for r in rows if
                           (chosen_status == "Tous les statuts" or r["RequestStatus"] == chosen_status)
                           and all(word in " ".join(str(r.get(f) or "") for f in ("RequestReference", "RequestReason", "ReportedAdress", "ReportedCity")).casefold()
                                   for word in query.casefold().split())]
                st.caption(f"{len(visible)} demande(s) sur {len(rows)} · Les plus récentes en premier")
                for row in visible:
                    with st.container(border=True):
                        info, action = st.columns([4, 1], vertical_alignment="center")
                        with info:
                            render_request_summary(row)
                        action.button("Voir la demande", key=f"forms_view_{row['RequestReference']}",
                                      on_click=open_request, args=(row["RequestReference"],), use_container_width=True)
                if not visible:
                    st.info("Aucune demande ne correspond à votre recherche. Essayez un autre mot ou un autre statut.")
        else:
            st.html('<div class="forms-empty"><h3>Votre première demande commence ici</h3><p>Utilisez le bouton Nouveau pour signaler des travaux. Vous retrouverez ensuite vos demandes et leur statut dans cet espace.</p></div>')
