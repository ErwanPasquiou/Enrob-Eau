
from pathlib import Path

import streamlit as st


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

STYLES_DIR = BASE_DIR / "styles"


# ============================================================
# CSS LOADER
# ============================================================

def load_css(*filenames: str):
    """
    Charge les fichiers CSS de l'application Enrob'Eau.

    Exemple :
        load_css("main.css", "header.css")
    """

    for filename in filenames:

        # Empêche de charger un fichier en dehors du dossier styles
        if Path(filename).name != filename:
            raise ValueError(
                f"Nom de fichier CSS invalide : {filename}"
            )

        if not filename.endswith(".css"):
            raise ValueError(
                f"Le fichier doit être au format CSS : {filename}"
            )

        css_path = STYLES_DIR / filename

        if not css_path.is_file():
            raise FileNotFoundError(
                f"Fichier CSS introuvable : {css_path}"
            )

        css_content = css_path.read_text(
            encoding="utf-8"
        )

        st.html(
            f"<style>{css_content}</style>"
        )