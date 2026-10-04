"""Vue complète d'une demande, réutilisable dans Forms."""
from datetime import datetime
from html import escape
import streamlit as st
from services.data_model import SCHEMAS, LABELS, DATE_FIELDS


def render_request_details(row):
    lines = []
    for field in SCHEMAS["demandes"]:
        value = row[field]
        if value is None or value == "":
            value = "Non renseigné"
        elif isinstance(value, bool):
            value = "Oui" if value else "Non"
        elif field in DATE_FIELDS:
            value = datetime.fromisoformat(value).strftime("%d/%m/%Y %H:%M" if "T" in value else "%d/%m/%Y")
        lines.append(f"<tr><th style='text-align:left'>{escape(LABELS[field])}</th><td>{escape(str(value))}</td></tr>")
    st.html("<table class='request-details'><tbody>" + "".join(lines) + "</tbody></table>")
