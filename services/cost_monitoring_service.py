"""Lecture FinOps et valorisation indicative, sans écriture Databricks."""
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import re

import pandas as pd

from services.administration_fallback import is_local_mode
from services.administration_service import get_connection
from services.auth_service import require_admin


class MonitoringUnavailable(RuntimeError):
    """La consommation ne peut pas être consultée ; ce n'est pas un coût nul."""


@dataclass(frozen=True)
class MonitoringScope:
    app_id: str
    warehouse_id: str
    start: date
    end: date
    usage_table: str = "system.billing.usage"

    def validate(self):
        for value in (self.app_id, self.warehouse_id):
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
                raise ValueError("Renseignez les identifiants de l’application et du Warehouse.")
        if self.start > self.end:
            raise ValueError("La date de début doit précéder la date de fin.")
        if (self.end - self.start).days >= 366:
            raise ValueError("Choisissez une période de 366 jours maximum.")
        if not re.fullmatch(r"[A-Za-z0-9_]+\.[A-Za-z0-9_]+\.[A-Za-z0-9_]+", self.usage_table):
            raise ValueError("La source de facturation doit être une table ou vue catalog.schema.nom.")


def authorize_monitoring():
    """Contrôle aussi les lectures en cache, et refuse l'identité de secours."""
    user = require_admin()
    if is_local_mode():
        raise MonitoringUnavailable(
            "Le suivi réel est indisponible en mode de secours local. "
            "Reconnectez l’administration à Databricks pour consulter les consommations."
        )
    return user


def _read(query, parameters):
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, parameters)
                rows = cursor.fetchall()
                columns = [column[0] for column in cursor.description]
        return pd.DataFrame.from_records([tuple(row) for row in rows], columns=columns)
    except Exception as exc:
        raise MonitoringUnavailable(
            "Lecture Databricks indisponible. Vérifiez la connexion et les droits de "
            "l’identité de l’application sur la source demandée. Aucun coût n’a été calculé."
        ) from exc


def load_usage(scope: MonitoringScope):
    authorize_monitoring()
    scope.validate()
    table = ".".join(f"`{part}`" for part in scope.usage_table.split("."))
    # Les rétractions sont négatives : conserver TOUS les record_type pour
    # compenser l'original avant d'ajouter un éventuel RESTATEMENT.
    query = f"""
        SELECT
            CASE WHEN usage_metadata.app_id = ? THEN 'application'
                 ELSE 'warehouse' END AS composant,
            usage_date AS jour,
            sku_name AS sku,
            usage_unit AS unite,
            SUM(usage_quantity) AS consommation,
            MAX(usage_end_time) AS derniere_consommation,
            MAX(ingestion_date) AS derniere_ingestion
        FROM {table}
        WHERE usage_date BETWEEN ? AND ?
          AND (usage_metadata.app_id = ? OR usage_metadata.warehouse_id = ?)
        GROUP BY 1, 2, 3, 4
        ORDER BY jour, composant, sku
    """
    return _read(query, [scope.app_id, scope.start, scope.end, scope.app_id, scope.warehouse_id])


def load_sql_activity(scope: MonitoringScope):
    authorize_monitoring()
    scope.validate()
    # Durée des requêtes démarrées dans la période UTC ; ne mesure ni le temps
    # de fonctionnement facturé du Warehouse, ni un usage exclusif Enrob'Eau.
    query = """
        SELECT COUNT(*) AS nombre_requetes,
               SUM(execution_duration_ms) / 1000.0 AS secondes_execution
        FROM system.query.history
        WHERE compute.warehouse_id = ?
          AND start_time >= CAST(? AS TIMESTAMP)
          AND start_time < CAST(? AS TIMESTAMP)
    """
    return _read(query, [
        scope.warehouse_id,
        f"{scope.start.isoformat()}T00:00:00Z",
        f"{(scope.end + timedelta(days=1)).isoformat()}T00:00:00Z",
    ])


def parse_rate(value):
    """None signifie tarif inconnu, 0 reste un tarif explicite valide."""
    if value is None or str(value).strip() == "":
        return None
    try:
        rate = Decimal(str(value).strip().replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError("Les tarifs doivent être des montants positifs en €/DBU.") from exc
    if not rate.is_finite() or rate < 0:
        raise ValueError("Les tarifs doivent être des montants positifs en €/DBU.")
    return rate


def summarize_usage(frame, app_rate, sql_rate, dedicated=False):
    """Aucun remplissage des jours absents ; coût de la consommation reçue seulement."""
    rates = {"application": parse_rate(app_rate), "warehouse": parse_rate(sql_rate)}
    result = {}
    for component, rate in rates.items():
        rows = frame.loc[frame["composant"] == component] if not frame.empty else frame
        present = not rows.empty
        dbu_only = present and rows["unite"].eq("DBU").all()
        quantities = []
        if dbu_only:
            for value in rows["consommation"]:
                try:
                    quantity = Decimal(str(value))
                except InvalidOperation as exc:
                    raise ValueError("Une consommation reçue est invalide.") from exc
                if not quantity.is_finite():
                    raise ValueError("Une consommation reçue est manquante ou invalide.")
                quantities.append(quantity)
        dbu = sum(quantities, Decimal(0)) if dbu_only else None
        cost = dbu * rate if dbu is not None and rate is not None else None
        result[component] = {"present": present, "dbu": dbu, "cost": cost, "rate": rate,
                             "unsupported_unit": present and not dbu_only}
    app_cost, sql_cost = result["application"]["cost"], result["warehouse"]["cost"]
    result["attributable"] = (
        app_cost + sql_cost if dedicated and app_cost is not None and sql_cost is not None
        else None if dedicated else app_cost
    )
    return result
