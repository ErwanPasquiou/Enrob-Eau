"""Scénario autonome de reporting ; aucune lecture ou écriture métier.

Les indicateurs décrivent la cohorte de demandes créées dans la période.
La date de référence est fixe pour garder la démonstration reproductible.
"""
from datetime import date, timedelta

AS_OF = date(2026, 10, 7)
PERIODS = {"12 derniers mois": 12, "6 derniers mois": 6, "3 derniers mois": 3}
CITIES = ("Saint-Étienne", "Saint-Héand", "Saint-Chamond", "Firminy", "Autres communes")
STATUSES = (
    ("À traiter", "#cbd7e7"),
    ("Intervention en cours", "#209fff"),
    ("Prestation réalisée", "#00a26a"),
    ("En attente de réfection définitive", "#ffbd16"),
    ("Clôturée", "#49a12e"),
)
MONTHS = ("Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Août", "Sept", "Oct", "Nov", "Déc")


def month_start(value, offset=0):
    index = value.year * 12 + value.month - 1 + offset
    year, month = divmod(index, 12)
    return date(year, month + 1, 1)


def demo_rows():
    """13 dossiers indépendants, dont 9 interventions réalisées et 12 conformes."""
    cities = [0, 1, 3, 0, 2, 0, 1, 2, 3, 0, 1, 4, 4]
    states = [3, 2, 1, 4, 2, 2, 3, 2, 1, 0, 1, 3, 0]
    created = ["2026-09-02", "2026-09-12", "2026-09-18", "2026-01-12", "2026-02-10",
               "2026-03-15", "2026-04-12", "2026-05-15", "2026-06-10", "2026-07-15",
               "2026-08-10", "2026-09-20", "2026-10-03"]
    refs = ["REQ-090", "REQ-012", "REQ-001", "REQ-009", "REQ-008", "REQ-007", "REQ-011",
            "REQ-014", "REQ-020", "REQ-021", "REQ-022", "REQ-023", "REQ-024"]
    delays = {0: 8, 1: 5, 3: 9, 4: 6, 5: 7, 6: 8, 7: 9, 10: 6, 11: 9}
    due = {0: date(2026, 9, 25), 1: date(2026, 10, 2), 2: date(2026, 10, 4),
           6: date(2026, 10, 10), 11: date(2026, 10, 14)}
    rows = []
    for i, ref in enumerate(refs):
        started = date.fromisoformat(created[i])
        delay = delays.get(i)
        rows.append(dict(reference=ref, city=CITIES[cities[i]], created=started,
                         address=("23 rue Étienne Ménard" if i == 0 else f"{11 + i} rue des Écoles"),
                         status=STATUSES[states[i]][0], status_index=states[i],
                         completed=started + timedelta(days=delay) if delay else None,
                         repaired=started + timedelta(days=delay + 3) if i == 3 else None,
                         delay=delay, compliant=i != 0, due=due.get(i),
                         photo_date=date(2026, 10, 3) - timedelta(days=i) if i < 6 else None))
    return rows


def metrics(rows):
    delays = [row["delay"] for row in rows if row["delay"] is not None]
    return (len(rows), len(delays), sum(row["status_index"] == 3 for row in rows),
            sum(delays) / len(delays) if delays else None,
            100 * sum(row["compliant"] for row in rows) / len(rows) if rows else None)


def snapshot(city="Toutes les communes", period="12 derniers mois"):
    months = PERIODS[period]
    start = month_start(AS_OF, 1 - months)
    rows = [r for r in demo_rows() if start <= r["created"] <= AS_OF
            and (city == "Toutes les communes" or r["city"] == city)]
    activity = []
    for offset in range(months):
        first = month_start(start, offset)
        following = month_start(first, 1)
        completed = [r for r in rows if r["completed"] and first <= r["completed"] < following]
        activity.append(dict(label=f"{MONTHS[first.month - 1]} {first.year}",
                             requests=sum(first <= r["created"] < following for r in rows),
                             completed=len(completed),
                             repaired=sum(bool(r["repaired"] and first <= r["repaired"] < following) for r in rows),
                             delay=sum(r["delay"] for r in completed) / len(completed) if completed else None))
    return dict(rows=rows, metrics=metrics(rows), activity=activity, start=start, end=AS_OF,
                statuses=[sum(r["status"] == label for r in rows) for label, _ in STATUSES],
                cities={name: sum(r["city"] == name for r in rows) for name in CITIES})


def priority_rows(rows, upcoming=False):
    return sorted((r for r in rows if r["due"] and r["status_index"] != 4
                   and (AS_OF <= r["due"] <= AS_OF + timedelta(days=14) if upcoming else r["due"] < AS_OF)),
                  key=lambda r: r["due"])
