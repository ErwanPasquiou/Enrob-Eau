
import streamlit as st

from components.styles import load_css

from components.page_content import (
    render_page_background,
)

from services.auth_service import (
    get_connected_email,
    get_current_user,
    PROFILS,
)


# ============================================================
# CONFIGURATION STREAMLIT
# ============================================================

st.set_page_config(
    page_title="Enrob'Eau",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# STYLES GLOBAUX
# ============================================================

load_css(
    "main.css",
    "header.css",
)


# ============================================================
# FOND COMMUN
# ============================================================

render_page_background()


# ============================================================
# IDENTIFICATION UTILISATEUR
# ============================================================

# Suppression de l'ancienne identité en session.
# Les droits sont revérifiés lors de chaque exécution.

st.session_state.pop(
    "current_user",
    None,
)


# ============================================================
# RECUPERATION DE L'EMAIL DATABRICKS
# ============================================================

email = get_connected_email()


# ------------------------------------------------------------
# IDENTITE NON DISPONIBLE
# ------------------------------------------------------------

if not email:

    st.title("Identification impossible")

    st.warning(
        "Nous ne pouvons pas vérifier votre identité "
        "pour le moment."
    )

    st.info(
        "Veuillez ouvrir Enrob'Eau depuis Databricks "
        "avec votre compte professionnel."
    )

    st.stop()


# ============================================================
# RECHERCHE DANS LA TABLE ADMINISTRATION
# ============================================================

try:

    user = get_current_user()

except Exception:

    st.error(
        "Le service de vérification des accès est "
        "temporairement indisponible."
    )

    st.info(
        "Veuillez réessayer ultérieurement ou contacter "
        "l'administrateur de l'application."
    )

    st.stop()


# ============================================================
# CONTROLE DES ACCES
# ============================================================

from services.administration_fallback import is_local_mode

if is_local_mode():
    st.warning(
        "Mode dégradé temporaire : les comptes et leurs modifications sont "
        "enregistrés localement avec des données de test. "
        "Aucune modification des comptes n'est envoyée à Databricks."
    )

if (
    user is None
    or not bool(user.get("actif"))
):

    st.title("Accès impossible")

    st.error(
        "Vous n'avez pas les droits nécessaires "
        "pour accéder à Enrob'Eau."
    )

    st.info(
        "Veuillez contacter l'administrateur "
        "de l'application pour demander un accès."
    )

    st.stop()


# ============================================================
# VERIFICATION DU PROFIL
# ============================================================

if user["profil"] not in PROFILS:

    st.error(
        "Votre profil utilisateur n'est pas reconnu. "
        "Veuillez contacter l'administrateur."
    )

    st.stop()


# ============================================================
# INFORMATIONS UTILISATEUR
# ============================================================

prenom = str(
    user.get("prenom") or ""
).strip()

nom = str(
    user.get("nom") or ""
).strip()


# ------------------------------------------------------------
# INITIALES DE L'UTILISATEUR
# ------------------------------------------------------------

initiales = (
    f"{prenom[:1]}{nom[:1]}"
).upper()


# ============================================================
# STOCKAGE DES INFORMATIONS UTILISATEUR
# ============================================================

st.session_state["current_user"] = {
    "id": int(user["id"]),
    "nom": nom,
    "prenom": prenom,
    "email": user["email"],
    "profil": user["profil"],
    "actif": bool(user["actif"]),
    "initials": initiales,
}


# ============================================================
# NAVIGATION SELON LE PROFIL
# ============================================================

from services.access_service import PAGES, can_access, default_page

pages_autorisees = [
    st.Page(script, title=title, url_path=url, default=key == default_page(user["profil"]))
    for key, title, script, url in PAGES
    if can_access(user["profil"], key)
]


# ============================================================
# NAVIGATION STREAMLIT
# ============================================================

page = st.navigation(
    pages_autorisees,
    position="hidden",
)


# ============================================================
# EXECUTION DE LA PAGE ACTIVE
# ============================================================

if st.query_params.get("photo"):
    from components.photo_viewer import render_photo_viewer
    render_photo_viewer()
else:
    page.run()
