"""Présentation du reporting : HTML/SVG local, sans dépendance graphique distante."""
from html import escape
from math import ceil

from services.reporting_demo_service import AS_OF, STATUSES


def icon(name):
    paths = {
        "chart": '<path d="M4 20V13h4v7zm6 0V8h4v12zm6 0V3h4v17z"/>',
        "file": '<path d="M6 3h8l4 4v14H6zM14 3v5h4M9 12h6M9 16h6"/>',
        "tool": '<path d="M14 4a5 5 0 0 0-6 6L3 17a2 2 0 0 0 4 3l6-7a5 5 0 0 0 7-6l-4 4-3-3 4-4z"/>',
        "hour": '<path d="M6 3h12M6 21h12M7 3c0 8 10 10 10 18M17 3c0 8-10 10-10 18M8 6h8M8 18h8"/>',
        "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',
        "check": '<circle cx="12" cy="12" r="9"/><path d="m7 12 3 3 7-7"/>',
    }
    return f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{paths[name]}</svg>'


def kpi_html(data):
    values = data["metrics"]
    labels = ("Demandes créées", "Interventions réalisées", "En attente de réfection définitive",
              "Délai moyen de traitement", "Taux de dossiers conformes")
    notes = ("Sur la période sélectionnée", "Interventions achevées", "Réfection à programmer",
             "Sur les interventions réalisées", "Conformité simulée")
    cards = []
    for i, (value, label, name, note) in enumerate(zip(values, labels, ("file", "tool", "hour", "clock", "check"), notes)):
        formatted = "—" if value is None else (f"{value:.1f} j".replace(".", ",") if i == 3 else f"{value:.0f}%" if i == 4 else str(value))
        cards.append(f'<article class="rp-kpi"><span class="rp-icon {"rp-green" if i == 4 else ""}">{icon(name)}</span>'
                     f'<div><strong>{formatted}</strong><span>{label}</span></div><small>{note}</small></article>')
    return '<section class="rp-summary"><div class="rp-intro"><div class="rp-intro-title">' + icon("chart") + '<h2>Une vision globale et fiable<br>de votre patrimoine voirie</h2></div><p>Suivez l’avancement des interventions, maîtrisez les délais<br>et disposez d’une donnée consolidée pour une meilleure prise de décision.</p></div>' + ''.join(cards) + '</section>'


def activity_svg(activity):
    width, height = 650, 245
    left, right, top, bottom = 42, 610, 20, 190
    maximum = max(4, max((r[k] for r in activity for k in ("requests", "completed", "repaired")), default=0))
    maximum = ceil(maximum / 4) * 4
    parts = [f'<svg class="rp-activity" viewBox="0 0 {width} {height}" role="img" aria-label="Évolution mensuelle des demandes, interventions, réfections et délais">']
    for tick in range(5):
        y = bottom - tick * (bottom - top) / 4
        parts.append(f'<path d="M{left} {y}H{right}" stroke="#e8edf5"/><text x="{left - 12}" y="{y + 4}" text-anchor="end">{tick * maximum // 4}</text><text x="{right + 12}" y="{y + 4}" class="rp-orange">{tick * 5}</text>')
    step = (right - left) / len(activity)
    bar = min(10, step / 5)
    points = []
    for i, row in enumerate(activity):
        x = left + step * (i + .5)
        for j, (key, color) in enumerate((("requests", "#55baff"), ("completed", "#0084ff"), ("repaired", "#13ac58"))):
            h = row[key] / maximum * (bottom - top)
            parts.append(f'<rect x="{x + (j - 1.5) * bar}" y="{bottom - h}" width="{bar - 1}" height="{h}" rx="1.5" fill="{color}"><title>{escape(row["label"])} : {row[key]} {key}</title></rect>')
        month, year = row["label"].split()
        parts.append(f'<text x="{x}" y="211" text-anchor="middle">{month}</text><text x="{x}" y="226" text-anchor="middle">{year}</text>')
        if row["delay"] is not None:
            points.append((x, bottom - row["delay"] / 20 * (bottom - top), row["delay"]))
        else:
            points.append(None)
    # Les mois sans intervention ne sont pas présentés comme un délai nul.
    previous = None
    for point in points:
        if point is None:
            previous = None
            continue
        x, y, delay = point
        if previous:
            parts.append(f'<path d="M{previous[0]} {previous[1]}L{x} {y}" stroke="#ff7416" stroke-width="2"/>')
        parts.append(f'<circle cx="{x}" cy="{y}" r="3.5" fill="#ff7416"><title>Délai moyen : {delay:.1f} jours</title></circle>')
        previous = point
    return ''.join(parts) + '</svg>'


def statuses_html(data):
    total = len(data["rows"])
    offset = 0
    arcs, legend = [], []
    for (label, color), count in zip(STATUSES, data["statuses"]):
        percentage = count / total * 100 if total else 0
        arcs.append(f'<circle cx="90" cy="90" r="65" fill="none" stroke="{color}" stroke-width="29" pathLength="100" stroke-dasharray="{percentage} {100 - percentage}" stroke-dashoffset="{-offset}" transform="rotate(-90 90 90)"/>')
        offset += percentage
        legend.append(f'<li><i style="background:{color}"></i><span>{escape(label)}</span><b>{count}</b><small>{percentage:.0f}%</small></li>')
    donut = '<svg viewBox="0 0 180 180" role="img" aria-label="Répartition des statuts">' + ''.join(arcs) + f'<text x="90" y="85" text-anchor="middle" class="rp-donut-total">{total}</text><text x="90" y="103" text-anchor="middle">dossiers</text><text x="90" y="117" text-anchor="middle">au total</text></svg>'
    return f'<div class="rp-status-layout">{donut}<ul class="rp-legend">{"".join(legend)}</ul></div>'


def map_html(data):
    positions = ((130, 114), (215, 56), (205, 190), (48, 169), (266, 153))
    bubbles = []
    legend = []
    for (name, count), (x, y) in zip(data["cities"].items(), positions):
        if count:
            bubbles.append(f'<circle cx="{x}" cy="{y}" r="{6 + count * 2}" fill="#39a8ff" fill-opacity=".55" stroke="#007dff"><title>{escape(name)} : {count} dossiers</title></circle><text x="{x}" y="{y - 20}" text-anchor="middle">{escape(name)}</text>')
        legend.append(f'<li><i style="background:#168cff"></i><span>{escape(name)}</span><b>{count}</b></li>')
    map_svg = '<svg class="rp-map" viewBox="0 0 320 225" role="img" aria-label="Carte schématique des communes, positions indicatives"><rect width="320" height="225" fill="#f2f6ef"/><path d="M0 60Q90 10 160 80T320 20M-10 180Q75 135 160 175T330 150M60 0Q120 95 65 225M240 0Q175 140 280 225" fill="none" stroke="#e2ecd9" stroke-width="28"/><path d="M-5 143Q75 160 130 114T215 56L250 -5M130 114L205 190 280 230M0 185L48 169 130 114 320 100" fill="none" stroke="white" stroke-width="9"/><path d="M-5 143Q75 160 130 114T215 56L250 -5M130 114L205 190 280 230M0 185L48 169 130 114 320 100" fill="none" stroke="#d8e0e9" stroke-width="2"/><path d="M310 0Q220 85 255 135T200 225" fill="none" stroke="#b7def6" stroke-width="3"/>' + ''.join(bubbles) + '</svg>'
    return f'<div class="rp-map-layout">{map_svg}<ul class="rp-legend rp-city-legend">{"".join(legend)}</ul></div><p class="rp-footnote">Carte schématique · emplacements indicatifs</p>'


def charts_html(data):
    legend = ''.join(f'<span><i style="background:{color}"></i>{label}</span>' for label, color in (
        ("Demandes créées", "#55baff"), ("Interventions réalisées", "#0084ff"),
        ("Réfections définitives", "#13ac58"), ("Délai moyen (jours)", "#ff7416")))
    return '<div class="rp-charts"><section class="rp-panel"><h2>Évolution de l’activité</h2>' + f'<div class="rp-chart-legend">{legend}</div>{activity_svg(data["activity"])}<p class="rp-footnote">À gauche : nombre de dossiers · à droite : délai en jours</p></section>' + '<section class="rp-panel"><h2>Répartition des statuts</h2>' + statuses_html(data) + '</section><section class="rp-panel"><h2>Activité par commune</h2>' + map_html(data) + '</section></div>'


def priorities_html(rows, upcoming=False):
    if not rows:
        return '<div class="rp-empty">Aucune échéance à venir sur 14 jours.</div>' if upcoming else '<div class="rp-empty">Aucun dossier en retard pour cette sélection.</div>'
    headings = ("Référence", "Commune", "Adresse / Localisation", "Statut", "Dans" if upcoming else "Jours de retard", "Échéance")
    lines = []
    for row in rows:
        days = abs((AS_OF - row["due"]).days)
        values = [escape(row[k]) for k in ("reference", "city", "address")]
        status = escape(row["status"])
        values += [f'<span class="rp-badge rp-status-{row["status_index"]}">{status}</span>',
                   f'<b class="{"rp-soon" if upcoming else "rp-late"}">{days} j</b>', row["due"].strftime("%d/%m/%Y")]
        lines.append('<tr>' + ''.join(f'<td>{value}</td>' for value in values) + '</tr>')
    return '<div class="rp-table-scroll" role="region" aria-label="Dossiers prioritaires" tabindex="0"><table class="rp-table"><thead><tr>' + ''.join(f'<th scope="col">{h}</th>' for h in headings) + '</tr></thead><tbody>' + ''.join(lines) + '</tbody></table></div>'


def photos_html(rows):
    photos = sorted((r for r in rows if r["photo_date"]), key=lambda r: r["photo_date"], reverse=True)[:6]
    if not photos:
        return '<p class="rp-empty">Aucune illustration pour cette sélection.</p>'
    cards = []
    for i, row in enumerate(photos):
        # Illustrations vectorielles explicites : aucun cliché réel n'est simulé.
        repair = '<path d="M65 35 121 30 140 83 58 85z" fill="#424c55" stroke="#303a43" stroke-width="2"/>'
        if i % 3 == 1:
            repair = '<path d="m115 34-15 49h32z" fill="#f47731"/><path d="M107 61h18l-3-10h-12" fill="white"/><rect x="96" y="82" width="41" height="5" rx="3" fill="#283947"/>'
        elif i % 3 == 2:
            repair = '<path d="M65 30h62l15 60H50z" fill="#ad8f70"/><path d="M72 32h44l9 58H61z" fill="#655747"/><path d="M65 63h58" stroke="#40a9dc" stroke-width="8"/>'
        illustration = '<svg viewBox="0 0 190 100" role="img" aria-label="Illustration fictive de travaux de voirie"><rect width="190" height="100" fill="#cbd8dd"/><path d="M0 30 190 14v86H0z" fill="#88969d"/><path d="M0 25 190 9M0 30 190 14" stroke="#e7e4d7" stroke-width="5"/><path d="M18 100 39 26M157 100 145 16" stroke="#f0ece0" stroke-width="3"/>' + repair + '</svg>'
        cards.append(f'<figure>{illustration}<figcaption>{escape(row["reference"])} – {escape(row["city"])}<br><span>{row["photo_date"].strftime("%d/%m/%Y")}</span></figcaption></figure>')
    return '<div class="rp-photo-grid">' + ''.join(cards) + '</div><p class="rp-footnote">Illustrations de démonstration · aucune photo réelle</p>'
