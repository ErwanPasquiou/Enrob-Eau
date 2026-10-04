from pathlib import Path
import math
import streamlit as st
import streamlit.components.v1 as components

_picker = components.declare_component("enrobeau_address", path=str(Path(__file__).parent / "address_picker"))


def address_fields(row, prefix):
    mode = st.radio("Adresse des travaux", ["Rechercher une adresse", "Autre / saisie libre"],
                    index=1 if row.get("ReportedAdress") else 0, horizontal=True, key=f"{prefix}_mode")
    if mode == "Rechercher une adresse":
        selected = _picker(initial=row.get("ReportedAdress") or "", key=f"{prefix}_picker", default=None)
        if isinstance(selected, dict) and selected.get("address") and selected.get("city"):
            result = {"ReportedAdress": str(selected["address"]), "ReportedCity": str(selected["city"])}
            landmark = ""
            try:
                lat, lon = float(selected["latitude"]), float(selected["longitude"])
                if math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180:
                    landmark = f"{lat:.6f}, {lon:.6f}"
            except (KeyError, TypeError, ValueError):
                pass
            result["LocationLandmark"] = landmark
            st.caption(f"Adresse retenue : {result['ReportedAdress']} · {result['ReportedCity']}")
            return result
        st.caption("Choisissez une proposition ou utilisez la saisie libre.")
        return None
    return {
        "ReportedAdress": st.text_input("Adresse signalée", value=row.get("ReportedAdress") or "", key=f"{prefix}_address", placeholder="Adresse ou lieu des travaux"),
        "ReportedCity": st.text_input("Commune", value=row.get("ReportedCity") or "", key=f"{prefix}_city", placeholder="Nom de la commune"),
        "LocationLandmark": st.text_input("Repères de localisation · GPS", value=row.get("LocationLandmark") or "", key=f"{prefix}_landmark", placeholder="Latitude, longitude de l'adresse"),
    }
