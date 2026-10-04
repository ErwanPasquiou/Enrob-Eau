"""Indicateurs de l'accueil calculés depuis le modèle de données d'exemple."""
import math
from datetime import datetime
import pandas as pd

CATEGORIES = {
    "demandes-attente": ("Demandes à traiter", "📋"),
    "interventions-cours": ("Interventions en cours", "🏗️"),
    "prestations-cours": ("Prestations en cours", "🚧"),
    "prestations-refection": ("Prestations en attente de réfection définitive", "🔧"),
}
COLUMNS = ["Référence", "Demande", "Commune", "Objet", "Date", "Statut"]


def coordinates(value):
    try:
        lat, lon = (float(part.strip()) for part in value.split("GPS :")[-1].split(","))
        if math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon
    except (AttributeError, TypeError, ValueError):
        pass
    return None


def home_data(store):
    requests = {r["RequestReference"]: r for r in store["demandes"]}
    orders = {r["WorkOrderReferenceEnrobEau"]: r for r in store["interventions"]}
    results = {key: [] for key in CATEGORIES}
    locations = []

    def record(ref, request, city, reason, when, status):
        return dict(zip(COLUMNS, [ref, request, city, reason,
                                 datetime.fromisoformat(when).strftime("%d/%m/%Y") if when else "Non renseignée", status]))

    for row in requests.values():
        if row["RequestStatus"] == "À traiter":
            results["demandes-attente"].append(record(row["RequestReference"], row["RequestReference"], row["ReportedCity"], row["RequestReason"], row["RequestDate"], row["RequestStatus"]))
    active_orders = set()
    for row in orders.values():
        if row["WorkOrderStatus"] == "En cours" and not row["ClosedAt"]:
            active_orders.add(row["WorkOrderReferenceEnrobEau"])
            parent = requests[row["RequestReference"]]
            results["interventions-cours"].append(record(row["WorkOrderReferenceSaur"], parent["RequestReference"], parent["ReportedCity"], parent["RequestReason"], row["IssuedAt"], row["WorkOrderStatus"]))
    seen_locations = set()
    for row in store["prestations"]:
        order = orders[row["WorkOrderReferenceEnrobEau"]]
        item = record(row["ServiceReference"], order["RequestReference"], row["WorkCity"], row["WorkReason"], row["CreatedAt"], row["ServiceStatus"])
        if row["ServiceStatus"] == "En cours" and not row["FinalRepairDate"]:
            results["prestations-cours"].append(item)
            if (row["HasTemporaryRepair"] or row["TemporaryRepairDate"]) and not row["FinalRepairDate"]:
                results["prestations-refection"].append(item)
        point = coordinates(row["WorkCoordinates"])
        if order["WorkOrderReferenceEnrobEau"] in active_orders and point:
            key = (order["WorkOrderReferenceEnrobEau"], *point)
            if key not in seen_locations:
                seen_locations.add(key)
                locations.append({"Référence": order["WorkOrderReferenceSaur"], "Commune": row["WorkCity"],
                                  "Objet": row["WorkReason"], "Statut": order["WorkOrderStatus"],
                                  "latitude": point[0], "longitude": point[1]})
    mapped_orders = {key[0] for key in seen_locations}
    for reference in sorted(active_orders - mapped_orders):
        order = orders[reference]
        request = requests[order["RequestReference"]]
        point = coordinates(request.get("LocationLandmark"))
        if point:
            locations.append({"Référence": order["WorkOrderReferenceSaur"], "Commune": request["ReportedCity"],
                              "Objet": request["RequestReason"], "Statut": order["WorkOrderStatus"],
                              "latitude": point[0], "longitude": point[1]})
    return ({key: pd.DataFrame(rows, columns=COLUMNS) for key, rows in results.items()},
            pd.DataFrame(locations, columns=["Référence", "Commune", "Objet", "Statut", "latitude", "longitude"]))
