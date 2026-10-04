
import base64

from pathlib import Path

import streamlit as st


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

ASSETS_DIR = BASE_DIR / "assets"


# ============================================================
# ASSET LOADER
# ============================================================

def _file_to_data_uri(path: Path) -> str:
    """
    Convertit une image locale en Data URI.
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
        f"data:{mime_types[extension]};base64,{encoded}"
    )


# ============================================================
# FOND DE PAGE
# ============================================================

def render_page_background():
    """
    Transmet l'image wave.svg au CSS global.

    Toutes les propriétés d'affichage du fond
    sont définies dans styles/main.css.
    """

    wave = _file_to_data_uri(
        ASSETS_DIR / "wave.svg"
    )

    st.html(
        f"""
        <style>
            :root {{
                --enrobeau-wave-image: url("{wave}");
            }}
        </style>
        """
    )


# ============================================================
# CONTENU DE PAGE
# ============================================================

def create_page_content():
    """
    Retourne un conteneur Streamlit classique
    avec l'espacement commun Enrob'Eau.
    """

    st.html(
        '<div class="enrobeau-page-spacer"></div>'
    )

    return st.container()