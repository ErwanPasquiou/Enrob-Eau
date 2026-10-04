"""Vue des prestations et de leur demande d'origine, sans chargement des photos."""


def prestation_rows(store):
    orders = {r["WorkOrderReferenceEnrobEau"]: r for r in store["interventions"]}
    # Projection d'affichage seulement : aucune référence SI SAUR stockée dans Service.
    return [dict(row, RequestReference=orders[row["WorkOrderReferenceEnrobEau"]]["RequestReference"],
                 WorkOrderReferenceSaur=orders[row["WorkOrderReferenceEnrobEau"]]["WorkOrderReferenceSaur"])
            for row in store["prestations"]]


def filter_prestations(rows, query="", cities=(), statuses=(), repair="Toutes"):
    query = query.strip().casefold()
    return [row for row in rows
            if (not query or query in " ".join(str(value or "") for value in row.values()).casefold())
            and (not cities or row["WorkCity"] in cities)
            and (not statuses or row["ServiceStatus"] in statuses)
            and (repair == "Toutes" or bool(row["FinalRepairDate"]) == (repair == "Réalisées"))]
