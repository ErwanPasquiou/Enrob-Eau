"""Politique de navigation partagée par le routeur, les pages et l'en-tête."""
import streamlit as st

PROFILS = ("agent", "ordonnanceur", "agent externe", "administrateur")
# Clé, titre, script, URL (la page d'accueil du rôle utilise toujours ./).
PAGES = (
    ("accueil", "Accueil", "pages/accueil.py", "accueil"),
    ("forms", "Demandes", "pages/forms.py", "forms"),
    ("refection", "Réfection définitive", "pages/reporting.py", "refection-definitive"),
    ("dossiers", "Gestion des dossiers", "pages/gestion_des_dossiers.py", "gestion-des-dossiers"),
    ("export", "Export", "pages/export.py", "export"),
    ("administration", "Administration", "pages/administration.py", "administration"),
)


def can_access(profile, page):
    if profile not in PROFILS or page not in {p[0] for p in PAGES}:
        return False
    if profile == "agent externe":
        return page == "refection"
    return page != "administration" or profile == "administrateur"


def default_page(profile):
    return {"agent": "forms", "agent externe": "refection"}.get(profile, "accueil")


def page_href(profile, key, url):
    return "./" if key == default_page(profile) else f"./{url}"


def require_page(page):
    user = st.session_state.get("current_user")
    if not user or not user.get("actif") or not can_access(user.get("profil"), page):
        st.error("Accès impossible : vous n'avez pas accès à cette page.")
        st.stop()
    return user
