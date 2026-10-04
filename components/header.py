
import base64

from html import escape
from pathlib import Path

import streamlit as st
from services.access_service import PAGES, can_access, page_href


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

ASSETS_DIR = BASE_DIR / "assets"


# ============================================================
# ASSET LOADER
# ============================================================

def file_to_data_uri(path: Path) -> str:
    """
    Convertit une image locale en Data URI afin
    de pouvoir l'utiliser directement dans le HTML.
    """

    if not path.exists():
        raise FileNotFoundError(
            f"Fichier introuvable : {path}"
        )

    mime_types = {
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }

    extension = path.suffix.lower()

    if extension not in mime_types:
        raise ValueError(
            f"Format non supporté : {extension}"
        )

    encoded = base64.b64encode(
        path.read_bytes()
    ).decode("utf-8")

    return (
        f"data:{mime_types[extension]};"
        f"base64,{encoded}"
    )


# ============================================================
# HEADER COMPONENT
# ============================================================

def render_header(
    active_page: str = "Accueil",
    initials: str = "",
    show_admin: bool = False,
):
    """
    Affiche le header principal Enrob'Eau.

    Paramètres
    ----------
    active_page :
        Nom de la page actuellement affichée.

    initials :
        Initiales de l'utilisateur connecté.

    show_admin :
        True si l'utilisateur peut accéder à
        la page Administration.
    """

    # ========================================================
    # ASSETS
    # ========================================================

    banner = file_to_data_uri(
        ASSETS_DIR / "banner.svg"
    )

    logo = file_to_data_uri(
        ASSETS_DIR / "logo-enrobeau-saur.png"
    )

    # ========================================================
    # NAVIGATION ACTIVE
    # ========================================================

    navigation_links = []
    profile = st.session_state.get("current_user", {}).get("profil")
    for key, title, _, url in PAGES:
        if key == "administration" or not can_access(profile, key):
            continue
        href = page_href(profile, key, url)
        css_class = "nav-item active" if active_page == title else "nav-item"
        current = ' aria-current="page"' if active_page == title else ""
        navigation_links.append(
            f'<a class="{css_class}" href="{href}" target="_self"'
            f' title="{escape(title)}"{current}>{escape(title)}</a>'
        )
    navigation_html = "".join(navigation_links)

    admin_class = (
        "admin-button active"
        if active_page == "Administration"
        else "admin-button"
    )

    # ========================================================
    # INFORMATIONS UTILISATEUR
    # ========================================================

    safe_initials = escape(
        str(initials).strip().upper()
    )

    # ========================================================
    # BOUTON ADMINISTRATION
    # ========================================================

    admin_link = ""

    if show_admin and can_access(profile, "administration"):

        admin_link = f"""
            <a
                class="{admin_class}"
                href="./administration"
                target="_self"
                title="Administration"
                aria-label="Administration"
            >
                &#9881;
            </a>
        """

    # ========================================================
    # HTML DU HEADER
    # ========================================================

    st.html(
        f"""
        <div class="enrobeau-header">

            <!-- ==========================================
                 IMAGE DE FOND
            =========================================== -->

            <img
                class="header-banner"
                src="{banner}"
                alt=""
            />


            <div class="header-content">


                <!-- ==========================================
                     LOGO ENROB'EAU
                =========================================== -->

                <a
                    class="brand-zone"
                    href="./"
                    target="_self"
                    title="Accueil"
                    aria-label="Retour à l'accueil"
                >

                    <img
                        class="brand-image"
                        src="{logo}"
                        alt="SAUR Enrob'Eau"
                    />

                </a>


                <!-- ==========================================
                     NAVIGATION PRINCIPALE
                =========================================== -->

                <nav class="nav-zone" aria-label="Navigation principale">
                    {navigation_html}
                </nav>


                <!-- ==========================================
                     ADMINISTRATION + UTILISATEUR
                =========================================== -->

                <div class="user-zone">


                    <!-- ======================================
                         BOUTON ADMINISTRATION
                    ======================================= -->

                    {admin_link}


                    <!-- ======================================
                         AVATAR UTILISATEUR
                    ======================================= -->

                    <div
                        class="avatar"
                        title="Utilisateur connecté"
                        aria-label="Utilisateur connecté : {safe_initials}"
                    >
                        {safe_initials}
                    </div>


                </div>


            </div>

        </div>
        """
    )
