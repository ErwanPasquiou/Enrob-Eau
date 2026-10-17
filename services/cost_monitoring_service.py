"""Suivi multi-ressources : DBU serveur et secondes d'exécution compute."""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import re

import pandas as pd

from services.administration_fallback import is_local_mode
from services.administration_service import get_connection
from services.auth_service import require_admin


COLUMNS = ["jour", "detail", "unite", "consommation", "nombre_requetes", "manquantes", "origine"]
KINDS = {"serveur": "Serveur App", "compute": "Compute SQL"}


class MonitoringUnavailable(RuntimeError):
    """Une indisponibilité ne représente pas une consommation nulle."""


def authorize_monitoring(real=True):
    user = require_admin()
    if real and is_local_mode():
        raise MonitoringUnavailable("Le suivi Databricks est indisponible en mode de secours local. Le jeu de démonstration reste accessible aux administrateurs.")
    return user


def parse_rate(value):
    if value is None or str(value).strip() == "":
        raise ValueError("Renseignez le tarif de la ressource.")
    try:
        rate = Decimal(str(value).strip().replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError("Le tarif doit être un nombre positif ou nul.") from exc
    if not rate.is_finite() or rate < 0 or rate > Decimal("1000000"):
        raise ValueError("Le tarif doit être compris entre 0 et 1 000 000.")
    return rate


def validate_resource(resource):
    name = str(resource.get("name", "")).strip()
    external_id = str(resource.get("external_id", "")).strip()
    if not name or len(name) > 80:
        raise ValueError("Donnez un nom à la ressource (80 caractères maximum).")
    if resource.get("kind") not in KINDS:
        raise ValueError("Choisissez un serveur ou un compute.")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", external_id):
        raise ValueError("Renseignez un identifiant valide (lettres, chiffres, tirets et underscores).")
    return dict(name=name, external_id=external_id, kind=resource["kind"],
                rate=str(parse_rate(resource.get("rate"))), shared=bool(resource.get("shared", False)) if resource["kind"] == "compute" else False)


def validate_period(start, end):
    if start > end:
        raise ValueError("La date de début doit précéder la date de fin.")
    if (end - start).days >= 1096:
        raise ValueError("Choisissez une période de trois ans maximum.")


def period_dates(period, today):
    if period in ("year", "previous_year", "two_years_ago"):
        year = today.year - {"year": 0, "previous_year": 1, "two_years_ago": 2}[period]
        return date(year, 1, 1), today if period == "year" else date(year, 12, 31)
    if period == "previous_month":
        end = today.replace(day=1) - timedelta(days=1)
        return end.replace(day=1), end
    if period == "30_days":
        return today - timedelta(days=29), today
    return today.replace(day=1), today


def _table_name(value):
    if not re.fullmatch(r"[A-Za-z0-9_]+\.[A-Za-z0-9_]+\.[A-Za-z0-9_]+", value):
        raise ValueError("La source doit être une table ou vue catalog.schema.nom.")
    return ".".join(f"`{part}`" for part in value.split("."))


def _read(query, parameters):
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SET TIME ZONE 'UTC'")
                cursor.execute(query, parameters)
                rows = cursor.fetchall()
                columns = [column[0] for column in cursor.description]
        return pd.DataFrame.from_records([tuple(row) for row in rows], columns=columns)
    except Exception as exc:
        raise MonitoringUnavailable("Lecture Databricks indisponible : vérifiez la connexion et les droits de l’application sur la source de cette ressource.") from exc


def load_resource_usage(resource, start, end, mode, usage_table="system.billing.usage", history_table="system.query.history"):
    if mode not in ("demo", "live"):
        raise ValueError("Source de données inconnue.")
    authorize_monitoring(real=mode == "live")
    resource = validate_resource(resource)
    validate_period(start, end)
    if mode == "demo":
        from services.cost_monitoring_demo import demo_usage
        return demo_usage(resource, start, end)
    if resource["kind"] == "serveur":
        # Conserver ORIGINAL, RETRACTION et RESTATEMENT et leurs signes.
        query = f"""
            SELECT usage_date AS jour, sku_name AS detail, usage_unit AS unite,
                   SUM(usage_quantity) AS consommation,
                   0 AS nombre_requetes, 0 AS manquantes
            FROM {_table_name(usage_table)}
            WHERE usage_metadata.app_id = ? AND usage_date BETWEEN ? AND ?
            GROUP BY usage_date, sku_name, usage_unit
            ORDER BY jour, detail
        """
        parameters = [resource["external_id"], start, end]
    else:
        query = f"""
            SELECT CAST(start_time AS DATE) AS jour,
                   COALESCE(executed_by, 'Utilisateur non renseigné') AS detail,
                   's' AS unite,
                   SUM(execution_duration_ms) / 1000.0 AS consommation,
                   COUNT(*) AS nombre_requetes,
                   SUM(CASE WHEN execution_duration_ms IS NULL THEN 1 ELSE 0 END) AS manquantes
            FROM {_table_name(history_table)}
            WHERE compute.warehouse_id = ?
              AND start_time >= CAST(? AS TIMESTAMP)
              AND start_time < CAST(? AS TIMESTAMP)
            GROUP BY CAST(start_time AS DATE), executed_by
            ORDER BY jour, detail
        """
        parameters = [resource["external_id"], f"{start.isoformat()}T00:00:00Z", f"{(end + timedelta(days=1)).isoformat()}T00:00:00Z"]
    frame = _read(query, parameters)
    frame["origine"] = "Databricks"
    return frame


def price_usage(frame, resource):
    """Pas d'arrondi intermédiaire ; les secondes ne sont jamais des DBU."""
    result = frame.copy()
    rate = parse_rate(resource["rate"])
    unit = "DBU" if resource["kind"] == "serveur" else "s"
    divisor = Decimal(1) if unit == "DBU" else Decimal(3600)
    quantities, costs = [], []
    for row in result.itertuples():
        try:
            value = Decimal(str(row.consommation))
        except InvalidOperation:
            value = Decimal("NaN")
        valid = value.is_finite() and row.unite == unit and (unit == "DBU" or value >= 0)
        quantities.append(value if valid else None)
        costs.append(value / divisor * rate if valid else None)
    result["consommation"] = quantities
    result["cout_eur"] = costs
    return result


def summarize_resource(priced):
    values = [value for value in priced.get("cout_eur", []) if value is not None and pd.notna(value)]
    quantities = [value for value in priced.get("consommation", []) if value is not None and pd.notna(value)]
    missing = int(priced["manquantes"].sum()) if not priced.empty else 0
    return {
        "cost": sum(values, Decimal(0)) if values else None,
        "quantity": sum(quantities, Decimal(0)) if quantities else None,
        "partial": len(values) != len(priced) or missing > 0,
        "queries": int(priced["nombre_requetes"].sum()) if not priced.empty else None,
    }
