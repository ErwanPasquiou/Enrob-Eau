"""Présentation des demandes personnelles."""
from datetime import datetime
from html import escape
import streamlit as st


def render_request_summary(row):
    status = row.get("RequestStatus") or "Non renseigné"
    tone = {"À traiter": "pending", "En cours": "active", "En attente": "waiting",
            "Clôturée": "closed", "Refusée": "declined"}.get(status, "pending")
    when = datetime.fromisoformat(row["RequestDate"]).strftime("%d/%m/%Y") if row.get("RequestDate") else "Non renseignée"
    st.html(f'''
        <article class="request-summary">
            <div class="request-summary-top">
                <span class="request-reference">{escape(row["RequestReference"])}</span>
                <span class="request-status request-status-{tone}">{escape(status)}</span>
            </div>
            <h3>{escape(row.get("RequestReason") or "Demande sans motif")}</h3>
            <div class="request-location">{escape(row.get("ReportedAdress") or "Adresse non renseignée")}</div>
            <div class="request-summary-bottom">
                <span>{escape(row.get("ReportedCity") or "Commune non renseignée")}</span>
                <span>Créée le {when}</span>
            </div>
        </article>
    ''')
