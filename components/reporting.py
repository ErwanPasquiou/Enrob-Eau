"""Présentation du reporting : HTML/SVG local, sans dépendance graphique distante."""
import base64
from collections import defaultdict
from html import escape
from math import ceil

import pydeck as pdk
import streamlit as st

from services.reporting_service import STATUSES


def svg_image(svg, css_class="", alt=""):
    """Les images SVG évitent le filtrage des balises SVG dans st.html."""
    svg = svg.replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', 1)
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f'<img class="{css_class}" src="data:image/svg+xml;base64,{encoded}" alt="{escape(alt, quote=True)}" />'


def icon(name):
    paths = {
        "chart": '<path d="M4 20V13h4v7zm6 0V8h4v12zm6 0V3h4v17z"/>',
        "file": '<path d="M6 3h8l4 4v14H6zM14 3v5h4M9 12h6M9 16h6"/>',
        "tool": '<path d="M14 4a5 5 0 0 0-6 6L3 17a2 2 0 0 0 4 3l6-7a5 5 0 0 0 7-6l-4 4-3-3 4-4z"/>',
        "hour": '<path d="M6 3h12M6 21h12M7 3c0 8 10 10 10 18M17 3c0 8-10 10-10 18M8 6h8M8 18h8"/>',
        "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',
        "check": '<circle cx="12" cy="12" r="9"/><path d="m7 12 3 3 7-7"/>',
    }
    color = "#00a263" if name == "check" else "#008aff"
    return svg_image(f'<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{paths[name]}</svg>')


def kpi_html(data):
    values = data["metrics"]
    labels = ("Demandes créées", "Interventions réalisées", "Prestations en attente de réfection définitive",
              "Délai moyen de traitement", "Conformité des données")
    notes = ("Selon la date de demande", "Clôturées et datées", "Réfection provisoire réalisée",
             "Demande → clôture d’intervention", "Validation des fiches du dossier")
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
    delay_maximum = max(20, ceil(max((r["delay"] or 0 for r in activity), default=0) / 4) * 4)
    parts = [f'<svg class="rp-activity" viewBox="0 0 {width} {height}" role="img" aria-label="Évolution mensuelle des demandes, interventions, réfections et délais">']
    parts.append('<style>text{fill:#355183;font:11px Arial,sans-serif}.rp-orange{fill:#f17718}</style>')
    for tick in range(5):
        y = bottom - tick * (bottom - top) / 4
        parts.append(f'<path d="M{left} {y}H{right}" stroke="#e8edf5"/><text x="{left - 12}" y="{y + 4}" text-anchor="end">{tick * maximum // 4}</text><text x="{right + 12}" y="{y + 4}" class="rp-orange">{tick * delay_maximum // 4}</text>')
    step = (right - left) / len(activity)
    bar = min(10, step / 5)
    points = []
    for i, row in enumerate(activity):
        x = left + step * (i + .5)
        for j, (key, color) in enumerate((("requests", "#55baff"), ("completed", "#0084ff"), ("repaired", "#13ac58"))):
            h = row[key] / maximum * (bottom - top)
            parts.append(f'<rect x="{x + (j - 1.5) * bar}" y="{bottom - h}" width="{bar - 1}" height="{h}" rx="1.5" fill="{color}"><title>{escape(row["label"])} : {row[key]} {key}</title></rect>')
        if i % max(1, ceil(len(activity) / 13)) == 0:
            label = row["label"].split()
            parts.append(f'<text x="{x}" y="211" text-anchor="middle">{escape(label[0])}</text>')
            if len(label) > 1:
                parts.append(f'<text x="{x}" y="226" text-anchor="middle">{escape(label[1])}</text>')
        if row["delay"] is not None:
            points.append((x, bottom - row["delay"] / delay_maximum * (bottom - top), row["delay"]))
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
    donut = '<svg viewBox="0 0 180 180"><style>text{fill:#355183;font:11px Arial,sans-serif}.rp-donut-total{font-size:25px;font-weight:bold;fill:#092866}</style><circle cx="90" cy="90" r="65" fill="none" stroke="#eef2f7" stroke-width="29"/>' + ''.join(arcs) + f'<text x="90" y="85" text-anchor="middle" class="rp-donut-total">{total}</text><text x="90" y="103" text-anchor="middle">dossiers</text><text x="90" y="117" text-anchor="middle">au total</text></svg>'
    return f'<div class="rp-status-layout">{svg_image(donut, "rp-donut", "Répartition des statuts des demandes")}<ul class="rp-legend">{"".join(legend)}</ul></div>'


def render_charts(data):
    panel_height = 480
    activity_column, status_column, map_column = st.columns([1.6, 1, 1.22], gap="small")
    with activity_column, st.container(height=panel_height, border=True):
        st.html('<h2 class="rp-section-title">Évolution de l’activité</h2>')
        legend = ''.join(f'<span><i style="background:{color}"></i>{label}</span>' for label, color in (
            ("Demandes créées", "#55baff"), ("Interventions réalisées", "#0084ff"),
            ("Réfections définitives", "#13ac58"), ("Délai moyen (jours)", "#ff7416")))
        st.html(f'<div class="rp-chart-legend">{legend}</div>'
                + svg_image(activity_svg(data["activity"]), "rp-activity", "Évolution des demandes, interventions clôturées, prestations réfectionnées et délai moyen")
                + '<p class="rp-footnote">À gauche : nombres de fiches · à droite : délai en jours</p>')
    with status_column, st.container(height=panel_height, border=True):
        st.html('<h2 class="rp-section-title">Répartition des statuts</h2>')
        st.html(statuses_html(data))
    with map_column, st.container(height=panel_height, border=True):
        st.html('<h2 class="rp-section-title">Activité par commune</h2>')
        render_map(data)


def render_map(data):
    grouped = defaultdict(list)
    for location in data["locations"]:
        grouped[(location["latitude"], location["longitude"])].append(location)
    points = []
    for (latitude, longitude), locations in grouped.items():
        references = sorted({r["reference"] for r in locations})
        cities = sorted({r["city"] for r in locations})
        points.append(dict(latitude=latitude, longitude=longitude, count=len(references),
                           radius=70 * len(references) ** .5,
                           tooltip=f"{', '.join(cities)}\n{len(references)} dossier(s)\n{', '.join(references)}"))
    if points:
        if len(points) == 1:
            view = pdk.ViewState(latitude=points[0]["latitude"], longitude=points[0]["longitude"], zoom=11)
        else:
            view = pdk.data_utils.compute_view([[p["longitude"], p["latitude"]] for p in points])
            view.zoom = max(1, min(view.zoom - 1, 12))
        st.pydeck_chart(pdk.Deck(
            map_provider="carto", map_style="light", initial_view_state=view, height=230,
            views=[pdk.View(type="MapView", height=230, controller=True)],
            layers=[pdk.Layer("ScatterplotLayer", data=points, get_position="[longitude, latitude]",
                              get_radius="radius", get_fill_color=[25, 149, 255, 160],
                              get_line_color=[0, 111, 225, 255], stroked=True,
                              radius_min_pixels=8, radius_max_pixels=35,
                              line_width_min_pixels=2, pickable=True)],
            tooltip={"text": "{tooltip}"}), use_container_width=True)
    else:
        st.info("Aucune coordonnée disponible pour cette sélection.")
    legend = ''.join(f'<li><i style="background:#168cff"></i><span>{escape(city)}</span><b>{count}</b></li>'
                     for city, count in data["cities"].items())
    st.html(f'<div class="rp-city-scroll" role="region" aria-label="Activité par commune" tabindex="0"><ul class="rp-legend rp-city-legend">{legend}</ul></div>')
    st.caption(f'{data["missing_locations"]} dossier(s) sans coordonnées. Les points superposés sont regroupés.')


def render_followup(rows, key):
    size = 50
    pages = max(1, ceil(len(rows) / size))
    if st.session_state.get(key, 1) > pages:
        st.session_state[key] = 1
    page = st.selectbox("Page des dossiers", range(1, pages + 1), key=key) if pages > 1 else 1
    st.html(followup_html(rows[(page - 1) * size:page * size]))
    if pages > 1:
        st.caption(f"{len(rows)} dossiers · {size} par page")


def followup_html(rows):
    if not rows:
        return '<div class="rp-empty">Aucun dossier pour cette sélection.</div>'
    headings = ("Référence", "Commune", "Adresse / Localisation", "Statut")
    lines = []
    for row in rows:
        values = [escape(row[k]) for k in ("reference", "city", "address")]
        values.append(f'<span class="rp-badge rp-status-{row["status_index"]}">{escape(row["status"])}</span>')
        lines.append('<tr>' + ''.join(f'<td>{value}</td>' for value in values) + '</tr>')
    return '<div class="rp-table-scroll" role="region" aria-label="Dossiers à suivre" tabindex="0"><table class="rp-table"><thead><tr>' + ''.join(f'<th scope="col">{h}</th>' for h in headings) + '</tr></thead><tbody>' + ''.join(lines) + '</tbody></table></div>'


def render_recent_photos(data):
    from services.reporting_service import recent_photos
    from services.photo_service import read_photo
    try:
        photos = recent_photos(data)
    except (OSError, ValueError) as exc:
        st.warning(f"Photos indisponibles : {exc}")
        return
    if not photos:
        st.info("Aucune photo enregistrée pour les dossiers sélectionnés.")
        return
    columns = st.columns(3)
    for i, photo in enumerate(photos):
        with columns[i % 3]:
            try:
                content = read_photo(photo["table"], photo["parent"], photo["PhotoReference"])
                st.image(content, use_column_width=True)
                st.caption(f'{photo["request"]} · {photo["PhotoName"]}')
            except (OSError, ValueError) as exc:
                st.caption(f"Photo indisponible : {exc}")
