"""Administration : comptes utilisateurs et suivi des consommations."""
import streamlit as st

from components.header import render_header
from components.page_content import create_page_content
from components.administration_users import render_user_administration
from components.cost_monitoring import render_cost_monitoring
from services.access_service import require_page

user = require_page("administration")
initials = f"{str(user.get('prenom') or '')[:1]}{str(user.get('nom') or '')[:1]}".upper()
render_header(active_page="Administration", initials=initials, show_admin=True)

with create_page_content():
    _, center, _ = st.columns([1, 18, 1])
    with center:
        st.title("Administration")
        st.caption("Gérez les accès et suivez les consommations d’Enrob’Eau.")
        section = st.radio(
            "Espace d’administration",
            ["Utilisateurs", "Consommation et coûts"],
            horizontal=True,
            key="admin_section",
            label_visibility="collapsed",
        )
        st.divider()
        if section == "Utilisateurs":
            render_user_administration()
        else:
            render_cost_monitoring()
