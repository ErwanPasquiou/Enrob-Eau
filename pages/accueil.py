import html
from urllib.parse import urlencode

from services.business_data_service import load_store
from services.home_service import CATEGORIES, home_data
import pydeck as pdk
import streamlit as st

from components.header import render_header
from components.page_content import create_page_content
from components.styles import load_css


# ============================================================
# HEADER
# ============================================================

# app.py identifie l'utilisateur et vérifie ses droits avant page.run().
from services.access_service import require_page
user = require_page("accueil")

prenom = str(user.get("prenom") or "").strip()
nom = str(user.get("nom") or "").strip()
initiales = f"{prenom[:1]}{nom[:1]}".upper()
safe_prenom = html.escape(prenom)

render_header(
    active_page="Accueil",
    initials=initiales,
    show_admin=(user.get("profil") == "administrateur"),
)


# ============================================================
# DONNÉES FICTIVES
# Source commune aux dossiers et aux exports : data/exemples
# ============================================================

try:
    store = load_store()
    category_data, map_locations = home_data(store)
except (OSError, ValueError) as exc:
    st.error(f"Impossible de charger les données d'exemple : {exc}")
    st.stop()


def dossiers_categorie(category):
    return category_data[category].copy()

def show_dossiers(category: str):
    title, _ = CATEGORIES[category]

    @st.dialog(title, width="large")
    def details():
        dossiers = dossiers_categorie(category)
        columns = ["Référence", "Demande", "Commune", "Objet", "Date", "Statut"]
        if dossiers.empty:
            st.info("Aucun dossier dans cette catégorie.")
        else:
            headers = "".join(f"<th scope='col'>{html.escape(column)}</th>" for column in columns)
            rows = []
            for values in dossiers[columns].itertuples(index=False, name=None):
                cells = []
                for column, value in zip(columns, values):
                    text = html.escape(str(value))
                    if column == "Statut":
                        text = f'<span class="dossier-status">{text}</span>'
                    cells.append(f"<td>{text}</td>")
                rows.append("<tr>" + "".join(cells) + "</tr>")
            st.html(
                '<div class="dossiers-table-scroll" tabindex="0" role="region" '
                'aria-label="Dossiers filtrés"><table class="dossiers-table">'
                f'<thead><tr>{headers}</tr></thead><tbody>{"".join(rows)}</tbody>'
                '</table></div>'
            )
        count, close = st.columns([4, 1])
        count.caption(f"{len(dossiers)} résultat(s)")
        if close.button("Fermer", type="primary", use_container_width=True):
            st.rerun()

    details()


# ============================================================
# STYLES SPECIFIQUES A L'ACCUEIL
# ============================================================

load_css("accueil.css")




# ============================================================
# PETIT COMPOSANT CARTE
# ============================================================

def metric_card(
    title: str,
    value: str,
    description: str,
    icon: str,
    category: str,
):
    """
    Carte métier simple sans iframe.
    La wave reste visible autour de la carte.
    """

    safe_title = html.escape(title)
    safe_value = html.escape(value)
    safe_description = html.escape(description)
    safe_icon = html.escape(icon)
    query = st.query_params.to_dict()
    query["suivi"] = category
    href = html.escape("?" + urlencode(query), quote=True)

    st.html(
        f"""
        <a class="metric-card" href="{href}" target="_self"
           aria-label="{safe_title} : {safe_value} dossiers, voir le détail">

            <div class="metric-card-icon">
                {safe_icon}
            </div>

            <div class="metric-card-title">
                {safe_title}
            </div>

            <div class="metric-card-value">
                {safe_value}
            </div>

            <div class="metric-card-description">
                {safe_description}
            </div>

            <div class="metric-card-detail">Voir le détail &#8594;</div>
        </a>
        """
    )


# ============================================================
# CONTENU PRINCIPAL
# ============================================================

content = create_page_content()


with content:

    # Marges générales de la page
    left_margin, center, right_margin = st.columns(
        [1, 18, 1],
        gap="small",
    )


    with center:

        # ====================================================
        # INTRODUCTION
        # ====================================================

        st.html(
            f"""
            <div class="home-intro">

                <div class="home-eyebrow">
                    Suivi des demandes, interventions et prestations
                </div>

                <h1 class="home-title">
                    Bonjour {safe_prenom} 👋 Environnement de développement
                </h1>

                <div class="home-description">
                    Retrouvez les opérations qui nécessitent votre attention
                    et suivez rapidement l'activité Enrob'Eau.
                </div>

            </div>
            """
        )


        # ====================================================
        # À TRAITER
        # ====================================================

        st.html(
            """
            <div class="home-section">

                <div class="home-section-title">
                    À traiter
                </div>

                <div class="home-section-description">
                    Données de test · La réfection définitive en attente est un sous-ensemble des prestations en cours.
                </div>

            </div>
            """
        )


        # ----------------------------------------------------
        # PREMIÈRE LIGNE DE CARTES
        # ----------------------------------------------------

        cards = st.columns(
            4,
            gap="medium",
        )


        for column, (category, (title, icon)) in zip(cards, CATEGORIES.items()):
            with column:
                metric_card(
                    title=title,
                    value=str(len(dossiers_categorie(category))),
                    description="",
                    icon=icon,
                    category=category,
                )


        # ====================================================
        # CARTE DES INTERVENTIONS EN COURS
        # ====================================================

        st.html(
            """
            <div class="home-section">

                <div class="home-section-title">
                    Interventions en cours - Carte
                </div>

                <div class="home-section-description">
                    Localisation des interventions en cours.
                </div>

            </div>
            """
        )


        interventions = dossiers_categorie("interventions-cours")
        locations = map_locations.copy()
        locations = locations.loc[
            locations["latitude"].between(-90, 90)
            & locations["longitude"].between(-180, 180)
        ].copy()
        if interventions.empty:
            st.info("Aucune intervention en cours.")
        elif locations.empty:
            st.info("Aucune localisation disponible pour les interventions en cours.")
        else:
            locations["tooltip"] = locations.apply(
                lambda row: f"{row['Référence']} - {row['Commune']}\n{row['Objet']}\n{row['Statut']}",
                axis=1,
            )
            points = locations[["longitude", "latitude"]].drop_duplicates()
            if len(points) == 1:
                view = pdk.ViewState(longitude=float(points.iloc[0]["longitude"]),
                                     latitude=float(points.iloc[0]["latitude"]), zoom=12)
            else:
                view = pdk.data_utils.compute_view(points.values.tolist())
                view.zoom = max(1, min(view.zoom - 1, 12))
            st.pydeck_chart(
                pdk.Deck(
                    map_provider="carto",
                    map_style="light",
                    initial_view_state=view,
                    layers=[pdk.Layer(
                        "ScatterplotLayer",
                        data=locations,
                        get_position="[longitude, latitude]",
                        get_fill_color=[36, 73, 136, 230],
                        get_line_color=[255, 255, 255],
                        get_radius=100,
                        radius_min_pixels=8,
                        radius_max_pixels=18,
                        stroked=True,
                        line_width_min_pixels=2,
                        pickable=True,
                    )],
                    tooltip={"text": "{tooltip}"},
                    height=360,
                ),
                use_container_width=True,
            )
            missing = len(interventions) - locations["Référence"].nunique()
            if missing:
                st.caption(f"{missing} intervention(s) sans localisation disponible.")
        st.caption("Données de data/exemples · Coordonnées des prestations liées ou de la demande. Plusieurs points peuvent se superposer.")


        # ====================================================
        # ESPACE DÉCORATIF AVANT LA WAVE
        # ====================================================

        st.html(
            """
            <div class="wave-safe-zone"></div>
            """
        )


# Consommer le filtre évite de rouvrir la fenêtre après sa fermeture.
selected_category = st.query_params.get("suivi")
if selected_category is not None:
    del st.query_params["suivi"]
    if selected_category in CATEGORIES:
        show_dossiers(selected_category)
