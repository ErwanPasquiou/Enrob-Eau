"""Historique reproductible de démonstration, fondé sur des captures anonymisées."""
from datetime import date, timedelta
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import pandas as pd

from services.cost_monitoring_service import COLUMNS


REFERENCE_PATH = Path(__file__).resolve().parents[1] / "data/exemples/finops_reference.json"


def reference_data():
    return json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))


def _allocate(total, weights):
    """Répartition entière déterministe, dont la somme reste exactement le total."""
    parts = [total * weight // sum(weights) for weight in weights]
    for index in range(total - sum(parts)):
        parts[index % len(parts)] += 1
    return parts


def demo_usage(resource, start, end):
    reference = reference_data()
    observed = {date.fromisoformat(day): Decimal(value) for day, value in reference["server_daily_dbu"]}
    samples = list(observed.values())
    anchor = date.fromisoformat(reference["simulation"]["compute_window_start"])
    baseline_id = "DEMO-SERVER-01" if resource["kind"] == "serveur" else "DEMO-COMPUTE-01"
    baseline = resource["external_id"] == baseline_id
    seed = int(hashlib.sha256(resource["external_id"].encode()).hexdigest()[:8], 16)
    resource_factor = Decimal(1) if baseline else Decimal(55 + seed % 50) / 100
    weights = [10, 10, 3, 2, 10, 10, 11]
    actors = []
    for actor in reference["compute_totals"]:
        queries = _allocate(actor["queries"], weights)
        # Une durée positive doit être rattachée à au moins une requête.
        seconds = _allocate(int(Decimal(actor["seconds"]) * 100), queries)
        actors.append((actor["actor"], seconds, queries))
    rows = []
    for offset in range((end - start).days + 1):
        day = start + timedelta(days=offset)
        day_index = (day - anchor).days
        year_factor = {2024: Decimal("0.7"), 2025: Decimal("0.85")}.get(day.year, Decimal(1))
        if resource["kind"] == "serveur":
            original = baseline and day in observed
            quantity = observed[day] if original else (samples[day.toordinal() % len(samples)] * year_factor * resource_factor).quantize(Decimal("0.000001"))
            origin = "Capture serveur" if original else "Historique simulé"
            rows.append([day, reference["server_sku"], "DBU", quantity, 0, 0, origin])
        else:
            reference_window = baseline and 0 <= day_index < 7
            variation = Decimal(1) if reference_window else Decimal(80 + ((day_index // 7) % 5) * 10) / 100
            factor = year_factor * resource_factor * variation
            for name, seconds, queries in actors:
                quantity = (Decimal(seconds[day_index % 7]) / 100 * factor).quantize(Decimal("0.01"))
                count = max(1 if quantity > 0 else 0, int(Decimal(queries[day_index % 7]) * factor))
                origin = "Total capture réparti sur dates fictives" if reference_window else "Historique simulé"
                rows.append([day, name, "s", quantity, count, 0, origin])
    return pd.DataFrame(rows, columns=COLUMNS)
