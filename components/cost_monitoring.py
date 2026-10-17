"""Espace administrateur : consommations observées et coûts indicatifs."""
from datetime import datetime, timedelta, timezone
import os

import pandas as pd
import streamlit as st

from services import cost_monitoring_service as finops
from services.business_data_service import export_csv


def _setting(name, default=""):
    if name in os.environ:
        return os.environ[name]
    try:
        return st.secrets.get(name, default)
    except FileNotFoundError:
        return default


def _default_settings():
    return {
        "app_id": str(_setting("FINOPS_APP_ID")),
        "warehouse_id": str(_setting("FINOPS_WAREHOUSE_ID", _setting("DATABRICKS_WAREHOUSE_ID"))),
        "app_rate": str(_setting("FINOPS_APP_EUR_PER_DBU", "1")),
        "sql_rate": str(_setting("FINOPS_SQL_EUR_PER_DBU")),
        "dedicated": str(_setting("FINOPS_WAREHOUSE_DEDICATED", "false")).lower() == "true",
    }


def _number(value, suffix=""):
    if value is None:
        return "Non disponible"
    return f"{value:,.2f}".replace(",", " ").replace(".", ",") + suffix


def _configuration():
    if "finops_settings" not in st.session_state:
        st.session_state.finops_settings = _default_settings()
    settings = st.session_state.finops_settings
    missing = not settings["app_id"] or not settings["warehouse_id"]
    with st.expander("Périmètre et tarifs", expanded=missing):
        st.caption("Ces réglages s’appliquent à votre session. Pour les conserver, configurez les variables de l’application décrites dans le README.")
        with st.form("finops_settings_form"):
            left, right = st.columns(2)
            app_id = left.text_input("Identifiant de l’application", settings["app_id"])
            warehouse_id = right.text_input("Identifiant du SQL Warehouse", settings["warehouse_id"])
            app_rate = left.text_input("Application · €/DBU", settings["app_rate"], help="Tarif de référence utilisé pour valoriser les DBU reçues.")
            sql_rate = right.text_input("Warehouse · €/DBU", settings["sql_rate"], help="Laissez vide tant que le tarif SQL n’est pas confirmé. Un tarif horaire ne doit pas être saisi ici.")
            dedicated = st.checkbox("Ce Warehouse est exclusivement dédié à Enrob’Eau", value=settings["dedicated"])
            st.caption("Un Warehouse partagé reste exclu du montant attribuable à Enrob’Eau. Son activité inclut les autres usages.")
            if st.form_submit_button("Appliquer les réglages"):
                candidate = dict(app_id=app_id.strip(), warehouse_id=warehouse_id.strip(), app_rate=app_rate.strip(), sql_rate=sql_rate.strip(), dedicated=dedicated)
                try:
                    today = datetime.now(timezone.utc).date()
                    finops.MonitoringScope(candidate["app_id"], candidate["warehouse_id"], today, today).validate()
                    finops.parse_rate(app_rate)
                    finops.parse_rate(sql_rate)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.session_state.finops_settings = candidate
                    settings = candidate
                    st.success("Réglages appliqués à cette session.")
    return settings


def _show_usage(frame, settings):
    summary = finops.summarize_usage(frame, settings["app_rate"], settings["sql_rate"], settings["dedicated"])
    app, warehouse = summary["application"], summary["warehouse"]
    first, second, third = st.columns(3)
    with first.container(border=True):
        st.metric("Application · coût estimé", _number(app["cost"], " €"))
        st.caption(f"{_number(app['dbu'], ' DBU')} · serveur de l’application")
    with second.container(border=True):
        st.metric("Warehouse · coût estimé", _number(warehouse["cost"], " €"))
        st.caption(f"{_number(warehouse['dbu'], ' DBU')} · {'dédié' if settings['dedicated'] else 'partagé, tous usages'}")
    with third.container(border=True):
        st.metric("Total estimé Enrob’Eau" if settings["dedicated"] else "Part attribuable · application seule", _number(summary["attributable"], " €"))
        st.caption("Application + Warehouse dédié" if settings["dedicated"] else "Coût SQL d’Enrob’Eau restant à attribuer")

    if not settings["dedicated"]:
        st.info("Warehouse partagé : sa consommation couvre tous les usages. Elle n’est pas ajoutée au coût de l’application.")
    for name, item in (("Application", app), ("Warehouse", warehouse)):
        if not item["present"]:
            st.warning(f"{name} : aucune consommation reçue sur cette période. Vérifiez le périmètre, les dates et le délai de publication ; cela ne signifie pas un coût nul.")
        elif item["unsupported_unit"]:
            st.warning(f"{name} : des unités autres que DBU sont présentes. Consultez le détail ; la conversion en euros est suspendue.")
        elif item["rate"] is None:
            st.info(f"{name} : DBU disponibles. Renseignez le tarif en €/DBU dans « Périmètre et tarifs » pour estimer le coût.")

    if frame.empty:
        return
    for component, label in (("application", "Application"), ("warehouse", "Warehouse")):
        rows = frame.loc[frame.composant == component]
        if not rows.empty:
            st.caption(f"{label} · dernière consommation reçue : {rows.derniere_consommation.max()} UTC · dernière ingestion : {rows.derniere_ingestion.max()}")
    st.subheader("Consommation quotidienne")
    dbu = frame.loc[frame.unite == "DBU"].copy()
    if not dbu.empty:
        dbu["consommation"] = pd.to_numeric(dbu["consommation"])
        dbu["composant"] = dbu["composant"].map({"application": "Application", "warehouse": "Warehouse"})
        daily = dbu.pivot_table(index="jour", columns="composant", values="consommation", aggfunc="sum")
        st.bar_chart(daily, color=["#006F8C", "#44BBA4"] if len(daily.columns) == 2 else "#006F8C")
        st.caption("DBU par jour UTC. Le Warehouse comprend tous ses usages. Les jours sans données ne sont pas remplacés par des consommations nulles.")
    with st.expander("Détail des consommations et export"):
        detail = frame.rename(columns={"composant": "Composant", "jour": "Jour UTC", "sku": "Type de facturation", "unite": "Unité", "consommation": "Consommation", "derniere_consommation": "Dernière consommation UTC", "derniere_ingestion": "Dernière ingestion"})
        st.dataframe(detail, hide_index=True, use_container_width=True)
        st.download_button("Télécharger les consommations (CSV)", export_csv(detail), file_name="enrobeau_consommations.csv", mime="text/csv")


def render_cost_monitoring():
    st.subheader("Consommation et coûts")
    st.caption("DBU enregistrées dans Databricks, valorisées avec vos tarifs de référence. Montants indicatifs sur la période, hors autres frais et marge interne.")
    settings = _configuration()
    today = datetime.now(timezone.utc).date()
    period = st.selectbox("Période", ["Mois en cours", "Mois précédent", "30 derniers jours", "Personnalisée"], key="finops_period")
    start, end = today.replace(day=1), today
    if period == "Mois précédent":
        end = start - timedelta(days=1)
        start = end.replace(day=1)
    elif period == "30 derniers jours":
        start = today - timedelta(days=29)
    elif period == "Personnalisée":
        left, right = st.columns(2)
        start = left.date_input("Du", value=start, max_value=today, key="finops_start")
        end = right.date_input("Au", value=end, max_value=today, key="finops_end")
    st.caption(f"Du {start:%d/%m/%Y} au {end:%d/%m/%Y} inclus · UTC. Publication différée, généralement sous 12 h ; la journée en cours peut être incomplète et des corrections peuvent arriver plus tard.")

    # Ne jamais servir une ancienne lecture à une identité de secours ou à un
    # utilisateur dont les droits viennent d'être retirés.
    try:
        user = finops.authorize_monitoring()
    except (PermissionError, finops.MonitoringUnavailable) as exc:
        st.session_state.pop("finops_snapshot", None)
        st.session_state.pop("finops_activity", None)
        st.warning(str(exc))
        return
    except Exception:
        st.error("Impossible de vérifier l’accès au suivi des coûts. Réessayez après rétablissement de la connexion.")
        return

    scope = finops.MonitoringScope(settings["app_id"], settings["warehouse_id"], start, end, str(_setting("FINOPS_USAGE_TABLE", "system.billing.usage")))
    try:
        scope.validate()
        finops.parse_rate(settings["app_rate"])
        finops.parse_rate(settings["sql_rate"])
    except ValueError as exc:
        st.info(str(exc))
        return
    # Cache limité à la session et indexé par identité, source, ressources et dates.
    key = (str(user.get("email")), scope)
    if st.session_state.get("finops_snapshot", {}).get("key") != key:
        st.session_state.pop("finops_snapshot", None)
    if st.session_state.get("finops_activity", {}).get("key") != key:
        st.session_state.pop("finops_activity", None)

    if st.button("Actualiser les consommations", type="primary", key="finops_refresh"):
        st.session_state.pop("finops_snapshot", None)
        try:
            with st.spinner("Lecture des consommations Databricks…"):
                frame = finops.load_usage(scope)
            st.session_state.finops_snapshot = dict(key=key, frame=frame, loaded_at=datetime.now(timezone.utc))
        except (PermissionError, finops.MonitoringUnavailable, ValueError) as exc:
            st.error(str(exc))

    snapshot = st.session_state.get("finops_snapshot")
    if snapshot:
        st.caption(f"Dernière lecture : {snapshot['loaded_at']:%d/%m/%Y à %H:%M} UTC. Actualisation manuelle ; aucune nouvelle lecture de facturation lors du changement de tarif.")
        try:
            _show_usage(snapshot["frame"], settings)
        except ValueError as exc:
            st.error(str(exc))
    else:
        st.info("Lancez une actualisation pour consulter les consommations de cette période.")

    with st.expander("Activité SQL du Warehouse"):
        st.write("La durée cumulée des requêtes sert à suivre l’activité. Elle ne correspond pas au temps facturé du Warehouse et ne sert pas à calculer son coût.")
        st.caption("Tous les utilisateurs et toutes les applications de ce Warehouse sont inclus. Les requêtes en cours et le délai de publication peuvent rendre le résultat incomplet.")
        if st.button("Charger l’activité SQL", key="finops_load_activity"):
            st.session_state.pop("finops_activity", None)
            try:
                activity = finops.load_sql_activity(scope)
                st.session_state.finops_activity = dict(key=key, frame=activity, loaded_at=datetime.now(timezone.utc))
            except (PermissionError, finops.MonitoringUnavailable, ValueError) as exc:
                st.error(str(exc))
        activity = st.session_state.get("finops_activity")
        if activity and not activity["frame"].empty:
            row = activity["frame"].iloc[0]
            left, right = st.columns(2)
            left.metric("Requêtes démarrées dans la période", int(row.nombre_requetes))
            right.metric("Exécution cumulée", _number(None if pd.isna(row.secondes_execution) else row.secondes_execution, " s"))
            st.caption(f"Activité lue le {activity['loaded_at']:%d/%m/%Y à %H:%M} UTC · source system.query.history")

    with st.expander("Comment lire ces montants ?"):
        st.markdown("Les consommations proviennent des ressources configurées, sans extrapolation annuelle. Le coût estimé correspond à **DBU reçues × tarif €/DBU** pour chaque ressource. Le tarif saisi s’applique à toute la période et à ses types de facturation ; il ne reconstitue pas une facture historique avec changements de prix ou remises.")
        st.markdown("Le suivi n’inclut pas Alfresco, le stockage, la maintenance, la marge interne ni les éventuels frais Azure facturés séparément du SQL Warehouse. Les corrections Databricks, y compris les rétractions négatives, sont conservées. Une période sans données ou sans tarif reste indiquée comme indisponible.")
