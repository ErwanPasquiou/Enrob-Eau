"""Agrégations en lecture seule des trois tables métier chargées par l'application."""
from calendar import monthrange
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from services.dossier_edit_service import validate_record
from services.home_service import coordinates

PERIODS = {"12 derniers mois": 12, "6 derniers mois": 6, "3 derniers mois": 3,
           "Dernier mois": 1, "Dernière semaine": 0}
STATUSES = (("À traiter", "#cbd7e7"), ("En cours", "#209fff"),
            ("En attente", "#ffbd16"), ("Refusée", "#e05b71"), ("Clôturée", "#00a26a"),
            ("Migration", "#9370db"))
MONTHS = ("Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Août", "Sept", "Oct", "Nov", "Déc")


def as_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)).date()
    except (TypeError, ValueError):
        return None


def month_start(value, offset=0):
    year, month = divmod(value.year * 12 + value.month - 1 + offset, 12)
    return date(year, month + 1, 1)


def period_bounds(period, today=None):
    end = today or date.today()
    months = PERIODS[period]
    if not months:
        return end - timedelta(days=6), end
    first = month_start(end, -months)
    previous = first.replace(day=min(end.day, monthrange(first.year, first.month)[1]))
    return previous + timedelta(days=1), end


def city_names(store):
    return sorted({r.get("ReportedCity") or "Commune non renseignée" for r in store["demandes"]})


def awaiting_repair(service):
    # Même règle que l'indicateur de l'accueil.
    return (service["ServiceStatus"] == "En cours"
            and bool(service.get("HasTemporaryRepair") or service.get("TemporaryRepairDate"))
            and not service.get("FinalRepairDate"))


def conformity_errors(request, orders, services):
    """Réutilise les validations de saisie, sans sauvegarde ni migration."""
    errors = []
    for table, records, key in (("demandes", [request], "RequestReference"),
                                ("interventions", orders, "WorkOrderReferenceEnrobEau"),
                                ("prestations", services, "ServiceReference")):
        for record in records:
            try:
                validate_record(table, record)
            except (ValueError, TypeError, KeyError, OverflowError) as exc:
                errors.append(f"{record[key]} : {exc}")
    return errors


def snapshot(store, city="Toutes les communes", period="12 derniers mois", today=None):
    start, end = period_bounds(period, today)
    requests = [r for r in store["demandes"] if as_date(r.get("RequestDate"))
                and start <= as_date(r["RequestDate"]) <= end
                and (city == "Toutes les communes" or (r.get("ReportedCity") or "Commune non renseignée") == city)]
    request_index = {r["RequestReference"]: r for r in requests}
    orders = [o for o in store["interventions"] if o["RequestReference"] in request_index]
    order_index = {o["WorkOrderReferenceEnrobEau"]: o for o in orders}
    services = [s for s in store["prestations"] if s["WorkOrderReferenceEnrobEau"] in order_index]
    orders_by_request, services_by_request = defaultdict(list), defaultdict(list)
    for order in orders:
        orders_by_request[order["RequestReference"]].append(order)
    for service in services:
        services_by_request[order_index[service["WorkOrderReferenceEnrobEau"]]["RequestReference"]].append(service)

    completed = [o for o in orders if o["WorkOrderStatus"] == "Clôturée"
                 and as_date(o.get("ClosedAt")) and start <= as_date(o["ClosedAt"]) <= end]
    repairs = [s for s in services if as_date(s.get("FinalRepairDate"))
               and start <= as_date(s["FinalRepairDate"]) <= end]
    delays = []
    for order in completed:
        closed = as_date(order["ClosedAt"])
        elapsed = (closed - as_date(request_index[order["RequestReference"]]["RequestDate"])).days
        if elapsed >= 0:
            delays.append((closed, elapsed))

    rows, locations = [], []
    for request in requests:
        reference = request["RequestReference"]
        linked_orders, linked_services = orders_by_request[reference], services_by_request[reference]
        errors = conformity_errors(request, linked_orders, linked_services)
        status = request["RequestStatus"]
        rows.append(dict(reference=reference, city=request.get("ReportedCity") or "Commune non renseignée",
                         address=request.get("ReportedAdress") or "Non renseignée",
                         created=as_date(request["RequestDate"]), status=status,
                         status_index=next((i for i, (label, _) in enumerate(STATUSES) if label == status), 0),
                         compliant=not errors, conformity_errors=errors))
        # Une demande peut avoir plusieurs chantiers ; dédoublonnage par demande/position.
        points = {point for service in linked_services if (point := coordinates(service.get("WorkCoordinates")))}
        if not points and (point := coordinates(request.get("LocationLandmark"))):
            points.add(point)
        for lat, lon in sorted(points):
            locations.append(dict(reference=reference, city=request.get("ReportedCity") or "Commune non renseignée",
                                  latitude=lat, longitude=lon))

    # Les dates de réalisation appartiennent aux enfants de la cohorte sélectionnée.
    daily = PERIODS[period] <= 1
    cursor = start if daily else month_start(start)
    activity = []
    while cursor <= end:
        following = cursor + timedelta(days=1) if daily else month_start(cursor, 1)
        values = [value for when, value in delays if cursor <= when < following]
        activity.append(dict(label=cursor.strftime("%d/%m") if daily else f"{MONTHS[cursor.month - 1]} {cursor.year}",
                             requests=sum(cursor <= r["created"] < following for r in rows),
                             completed=sum(cursor <= as_date(o["ClosedAt"]) < following for o in completed),
                             repaired=sum(cursor <= as_date(s["FinalRepairDate"]) < following for s in repairs),
                             delay=sum(values) / len(values) if values else None))
        cursor = following
    count = len(rows)
    return dict(rows=rows, orders=orders, services=services, locations=locations,
                metrics=(count, len(completed), sum(awaiting_repair(s) for s in services),
                         sum(value for _, value in delays) / len(delays) if delays else None,
                         100 * sum(r["compliant"] for r in rows) / count if count else None),
                activity=activity, start=start, end=end,
                statuses=[sum(r["status"] == label for r in rows) for label, _ in STATUSES],
                cities=dict(sorted(Counter(r["city"] for r in rows).items())),
                missing_locations=count - len({r["reference"] for r in locations}),
                undated_requests=sum(not as_date(r.get("RequestDate")) for r in store["demandes"]
                                     if city == "Toutes les communes" or (r.get("ReportedCity") or "Commune non renseignée") == city),
                excluded_delays=len(completed) - len(delays))


def recent_photos(data):
    """Métadonnées des six dernières photos liées, sans créer une base absente."""
    from services import business_data_service
    from services.photo_service import connection, TABLES, METADATA
    if not (business_data_service.DATA_DIR / "photos.sqlite3").is_file():
        return []
    parents = [("demandes", r["reference"], r["reference"]) for r in data["rows"]]
    orders = {o["WorkOrderReferenceEnrobEau"]: o for o in data["orders"]}
    parents += [("prestations", s["ServiceReference"], orders[s["WorkOrderReferenceEnrobEau"]]["RequestReference"])
                for s in data["services"]]
    photos = []
    # Requêtes groupées : ne pas recharger les 4 000 demandes pour chaque parent.
    with connection() as db:
        for table, (sql_table, parent_field) in TABLES.items():
            references = {parent: request for kind, parent, request in parents if kind == table}
            keys = list(references)
            for offset in range(0, len(keys), 400):
                batch = keys[offset:offset + 400]
                placeholders = ','.join('?' for _ in batch)
                records = db.execute(
                    f'SELECT {parent_field}, {METADATA} FROM {sql_table} '
                    f'WHERE {parent_field} IN ({placeholders}) '
                    'ORDER BY CreatedAt DESC, PhotoReference DESC LIMIT 6', batch)
                for photo in records:
                    parent = photo[parent_field]
                    photos.append(dict(photo, table=table, parent=parent, request=references[parent]))
    return sorted(photos, key=lambda p: (p.get("CreatedAt") or "", p["PhotoReference"]), reverse=True)[:6]
