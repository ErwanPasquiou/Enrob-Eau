"""Administration des suivis et tableaux de bord FinOps."""
from datetime import datetime, timezone
from decimal import Decimal
import os

import pandas as pd
import streamlit as st

from services import cost_monitoring_service as finops
from services import finops_resource_service as resources
from services.business_data_service import export_csv


def _setting(name, default=""):
    if name in os.environ:
        return os.environ[name]
    try:
        return st.secrets.get(name, default)
    except FileNotFoundError:
        return default


def _live_defaults():
    defaults = []
    app_id = str(_setting("FINOPS_APP_ID"))
    compute_id = str(_setting("FINOPS_WAREHOUSE_ID", _setting("DATABRICKS_WAREHOUSE_ID")))
    if app_id:
        defaults.append(dict(name="Enrob’Eau · serveur", kind="serveur", external_id=app_id,
                             rate=_setting("FINOPS_APP_EUR_PER_DBU", "1"), shared=False))
    if compute_id:
        defaults.append(dict(name="Enrob’Eau · compute", kind="compute", external_id=compute_id,
                             rate=_setting("FINOPS_COMPUTE_EUR_PER_HOUR", "0.9"),
                             shared=str(_setting("FINOPS_WAREHOUSE_DEDICATED", "false")).lower() != "true"))
    return defaults


def _number(value, suffix="", digits=2):
    if value is None or pd.isna(value):
        return "Non disponible"
    return f"{value:,.{digits}f}".replace(",", " ").replace(".", ",") + suffix


def _save_resource(mode, existing, kind, prefix):
    values = dict(name=st.session_state[f"{prefix}_name"], external_id=st.session_state[f"{prefix}_id"],
                  rate=st.session_state[f"{prefix}_rate"], kind=kind,
                  shared=st.session_state.get(f"{prefix}_shared", False))
    try:
        resource_id = resources.save_resource(mode, values, existing["id"] if existing else None,
                                             existing["version"] if existing else None)
    except (ValueError, OSError, PermissionError) as exc:
        st.session_state.finops_dialog_error = str(exc)
    else:
        st.session_state.finops_saved_id = resource_id
        st.session_state.finops_flash = "Suivi modifié." if existing else "Suivi ajouté."
        st.session_state.finops_close_dialog = True


@st.dialog("Suivi d’une ressource", width="large")
def resource_dialog(mode, existing=None):
    if st.session_state.pop("finops_close_dialog", False):
        st.rerun()
    st.subheader("Modifier le suivi" if existing else "Ajouter un suivi")
    st.caption("Données de démonstration" if mode == "demo" else "Données Databricks")
    if error := st.session_state.pop("finops_dialog_error", None):
        st.error(error)
    kinds = list(finops.KINDS)
    key = f"finops_editor_{mode}_{existing['id'] + '_' + str(existing['version']) if existing else 'new'}"
    kind = st.selectbox("Type de ressource", kinds, index=kinds.index(existing["kind"]) if existing else 0,
                        format_func=finops.KINDS.get, disabled=existing is not None, key=f"{key}_kind")
    unit = "€/DBU" if kind == "serveur" else "€/h d’exécution"
    prefix = f"{key}_{kind}"
    with st.form(f"{prefix}_form"):
        name = st.text_input("Nom du suivi", value=existing["name"] if existing else "", max_chars=80, key=f"{prefix}_name")
        external_id = st.text_input("Identifiant de l’application" if kind == "serveur" else "Identifiant du SQL Warehouse",
                                    value=existing["external_id"] if existing else "", key=f"{prefix}_id")
        rate = st.text_input(f"Tarif · {unit}", value=existing["rate"] if existing else ("1" if kind == "serveur" else "0,90"), key=f"{prefix}_rate")
        shared = st.checkbox("Compute partagé avec d’autres applications", value=bool(existing["shared"]) if existing else True, key=f"{prefix}_shared") if kind == "compute" else False
        st.caption("Le tarif saisi s’applique à toute la période consultée. Les réglages sont enregistrés sur cette instance de l’application.")
        if mode == "demo":
            st.caption("Ce suivi utilise un historique fictif : aucune lecture des tables système Databricks n’est effectuée.")
        st.form_submit_button("Enregistrer", type="primary", on_click=_save_resource, args=(mode, existing, kind, prefix))
    if st.button("Annuler", key=f"{key}_cancel"):
        st.rerun()


def _period(today):
    labels = {
        "year": f"Depuis le début de l’année · {today.year}",
        "previous_year": f"Année N−1 · {today.year - 1}",
        "two_years_ago": f"Année N−2 · {today.year - 2}",
        "month": "Mois en cours", "previous_month": "Mois précédent",
        "30_days": "30 derniers jours", "custom": "Personnalisée",
    }
    period = st.selectbox("Période", list(labels), format_func=labels.get, key="finops_v2_period")
    start, end = finops.period_dates(period, today)
    if period == "custom":
        start = st.date_input("Du", value=start, max_value=today, key="finops_v2_start")
        end = st.date_input("Au", value=end, max_value=today, key="finops_v2_end")
    return start, end


def _resource_controls(mode, rows):
    settings, action = st.columns([5, 1])
    if action.button("Ajouter", key="finops_add", use_container_width=True):
        resource_dialog(mode)
    if not rows:
        st.info("Ajoutez un serveur App ou un compute SQL pour démarrer le suivi.")
        return []
    names = {row["id"]: row["name"] for row in rows}
    key = f"finops_selection_{mode}"
    selected = st.session_state.get(key, list(names))
    selected = [resource_id for resource_id in selected if resource_id in names]
    saved = st.session_state.pop("finops_saved_id", None)
    if saved in names and saved not in selected:
        selected.append(saved)
    st.session_state[key] = selected
    with settings.expander(f"Ressources suivies · {len(rows)} · gérer et filtrer"):
        selected = st.multiselect("Ressources affichées", list(names), format_func=names.get, key=key)
        for row in rows:
            st.write(row["name"])
            tariff = _number(Decimal(row["rate"]), " €/DBU" if row["kind"] == "serveur" else " €/h")
            st.caption(f"{finops.KINDS[row['kind']]} · {row['external_id']} · {tariff}" + (" · Partagé" if row["shared"] else ""))
            if st.button("Modifier", key=f"finops_edit_{row['id']}"):
                resource_dialog(mode, row)
    return [row for row in rows if row["id"] in selected]


def _display_results(rows, snapshot, mode, start, end):
    summaries, details = [], []
    for resource in rows:
        result = snapshot["results"].get(resource["id"], {})
        frame = result.get("frame", pd.DataFrame(columns=finops.COLUMNS))
        priced = finops.price_usage(frame, resource)
        summary = finops.summarize_resource(priced)
        status = "Indisponible" if result.get("error") else "Aucune donnée" if priced.empty else "Partiel" if summary["partial"] else "Disponible"
        summaries.append(dict(resource=resource, **summary, status=status))
        if result.get("error"):
            st.warning(f"{resource['name']} : {result['error']}")
        elif priced.empty:
            st.info(f"{resource['name']} : aucune donnée sur cette période. Ce n’est pas un coût nul.")
        elif summary["partial"]:
            st.warning(f"{resource['name']} : résultat partiel (durées manquantes, valeurs ou unités non exploitables).")
        if not priced.empty:
            priced["ressource"] = resource["name"]
            priced["resource_id"] = resource["id"]
            priced["type"] = finops.KINDS[resource["kind"]]
            priced["tarif"] = resource["rate"]
            details.append(priced)

    totals = {}
    for kind in ("serveur", "compute", "all"):
        costs = [item["cost"] for item in summaries if item["cost"] is not None and (kind == "all" or item["resource"]["kind"] == kind)]
        totals[kind] = sum(costs, Decimal(0)) if costs else None
    partial = any(item["status"] != "Disponible" for item in summaries)
    for col, title, value in zip(st.columns(3), ["Serveurs App", "Computes SQL", "Total disponible · partiel" if partial else "Total du périmètre suivi"], [totals["serveur"], totals["compute"], totals["all"]]):
        with col.container(border=True):
            st.metric(title, _number(value, " €"))
    if any(row["shared"] for row in rows):
        st.caption("Le total inclut les computes partagés sélectionnés, tous utilisateurs confondus. Il ne représente pas le seul coût d’Enrob’Eau.")
    st.caption("Serveur : DBU × €/DBU. Compute : secondes d’exécution ÷ 3 600 × €/h. Montants estimés selon les tarifs configurés.")

    graph_tab, table_tab = st.tabs(["Graphiques", "Tableaux"])
    detail = pd.concat(details, ignore_index=True) if details else pd.DataFrame()
    with graph_tab:
        if detail.empty:
            st.info("Le graphique apparaîtra lorsque des consommations seront disponibles.")
        else:
            grain = st.radio("Regrouper par", ["Mois", "Jour"], horizontal=True, key="finops_grain")
            plot = detail.dropna(subset=["cout_eur"]).copy()
            plot["Période"] = pd.to_datetime(plot["jour"])
            if grain == "Mois":
                plot["Période"] = plot["Période"].dt.to_period("M").dt.to_timestamp()
            plot["Coût estimé (€)"] = plot["cout_eur"].map(float)
            if not plot.empty:
                chart = plot.pivot_table(index="Période", columns="resource_id", values="Coût estimé (€)", aggfunc="sum")
                labels = {row["id"]: row["name"] if sum(other["name"] == row["name"] for other in rows) == 1 else f"{row['name']} · {finops.KINDS[row['kind']]} · {row['external_id']}" for row in rows}
                chart = chart.rename(columns=labels)
                st.subheader("Évolution des coûts estimés")
                st.bar_chart(chart, y_label="Coût estimé (€)")
            names = {row["id"]: row["name"] for row in rows}
            chosen = st.selectbox("Consommation d’une ressource", list(names), format_func=names.get, key="finops_chart_resource")
            resource = next(row for row in rows if row["id"] == chosen)
            quantities = detail.loc[detail.resource_id == chosen].dropna(subset=["consommation"]).copy()
            if not quantities.empty:
                quantities["Période"] = pd.to_datetime(quantities["jour"])
                if grain == "Mois":
                    quantities["Période"] = quantities["Période"].dt.to_period("M").dt.to_timestamp()
                label = "Consommation (DBU)" if resource["kind"] == "serveur" else "Exécution cumulée (s)"
                quantities[label] = quantities["consommation"].map(float)
                st.bar_chart(quantities.groupby("Période")[[label]].sum(), y_label=label, color="#006F8C")
            st.caption("Les DBU et les secondes sont affichées séparément. Les périodes absentes ne sont pas remplacées par des zéros.")
    with table_tab:
        overview = pd.DataFrame([{
            "Ressource": item["resource"]["name"], "Type": finops.KINDS[item["resource"]["kind"]],
            "Consommation": float(item["quantity"]) if item["quantity"] is not None else None,
            "Unité": "DBU" if item["resource"]["kind"] == "serveur" else "s",
            "Tarif": _number(Decimal(item["resource"]["rate"]), " €/DBU" if item["resource"]["kind"] == "serveur" else " €/h"),
            "Coût estimé (€)": float(item["cost"]) if item["cost"] is not None else None,
            "État": item["status"],
        } for item in summaries])
        st.subheader("Synthèse par ressource")
        st.dataframe(overview, hide_index=True, use_container_width=True,
                     column_config={"Coût estimé (€)": st.column_config.NumberColumn(format="%.2f €"),
                                    "Consommation": st.column_config.NumberColumn(format="%.2f")})
        _download(overview, "synthese", mode, start, end)
        if not detail.empty:
            compute = detail.loc[detail["type"] == finops.KINDS["compute"]].copy()
            if not compute.empty:
                with st.expander("Compute · répartition par utilisateur"):
                    by_actor = compute.groupby(["resource_id", "ressource", "detail"], dropna=False)[["consommation", "nombre_requetes", "cout_eur"]].sum(min_count=1).reset_index()
                    by_actor = by_actor.drop(columns=["resource_id"]).rename(columns={"ressource": "Ressource", "detail": "Utilisateur", "consommation": "Exécution (s)", "nombre_requetes": "Requêtes", "cout_eur": "Coût estimé (€)"})
                    by_actor["Exécution (s)"] = pd.to_numeric(by_actor["Exécution (s)"])
                    by_actor["Coût estimé (€)"] = pd.to_numeric(by_actor["Coût estimé (€)"])
                    st.dataframe(by_actor.sort_values("Exécution (s)", ascending=False), hide_index=True, use_container_width=True,
                                 column_config={"Exécution (s)": st.column_config.NumberColumn(format="%.2f"),
                                                "Coût estimé (€)": st.column_config.NumberColumn(format="%.2f €")})
            st.subheader("Détail des consommations")
            formatted = detail.drop(columns=["resource_id"]).rename(columns={"jour": "Jour UTC", "detail": "Utilisateur / type de facturation", "unite": "Unité", "consommation": "Consommation", "nombre_requetes": "Requêtes", "manquantes": "Durées manquantes", "origine": "Origine", "cout_eur": "Coût estimé (€)", "ressource": "Ressource", "type": "Type", "tarif": "Tarif de référence"})
            display = formatted.copy()
            display["Coût estimé (€)"] = pd.to_numeric(display["Coût estimé (€)"])
            display["Consommation"] = pd.to_numeric(display["Consommation"])
            st.dataframe(display, hide_index=True, use_container_width=True,
                         column_order=["Ressource", "Jour UTC", "Consommation", "Unité", "Coût estimé (€)", "Utilisateur / type de facturation", "Requêtes", "Origine", "Tarif de référence", "Type", "Durées manquantes"],
                         column_config={"Coût estimé (€)": st.column_config.NumberColumn(format="%.2f €"),
                                        "Consommation": st.column_config.NumberColumn(format="%.2f"),
                                        "Utilisateur / type de facturation": st.column_config.TextColumn(width="medium")})
            _download(formatted, "detail", mode, start, end)


def _download(frame, name, mode, start, end):
    exported = frame.assign(Source="DÉMONSTRATION" if mode == "demo" else "Databricks", Debut=start, Fin=end)
    st.download_button("Exporter la synthèse" if name == "synthese" else "Exporter le détail", export_csv(exported),
                       file_name=f"enrobeau_{mode}_{name}_{start}_{end}.csv", mime="text/csv", key=f"finops_export_{name}")


def render_cost_monitoring():
    st.session_state.pop("finops_close_dialog", None)
    st.subheader("Consommation et coûts")
    today = datetime.now(timezone.utc).date()
    source_col, period_col = st.columns(2)
    with source_col:
        source = st.radio("Source des données", ["Démonstration", "Databricks"], horizontal=True, key="finops_source")
    with period_col:
        start, end = _period(today)
    mode = "demo" if source == "Démonstration" else "live"
    try:
        user = finops.authorize_monitoring(real=False)
        rows = resources.list_resources(mode, _live_defaults() if mode == "live" else ())
    except (PermissionError, OSError, ValueError) as exc:
        st.session_state.pop("finops_v2_snapshot", None)
        st.error(str(exc))
        return
    except Exception:
        st.session_state.pop("finops_v2_snapshot", None)
        st.error("Impossible de vérifier les accès au suivi. Réessayez après rétablissement de la connexion.")
        return
    if mode == "demo":
        st.warning("DÉMONSTRATION · historique simulé à partir des captures, utilisateurs anonymisés. Ces montants ne sont pas des coûts réels.")
    else:
        st.caption("Lecture manuelle de system.billing.usage pour les serveurs et de system.query.history pour les computes. Aucune substitution par des données de démonstration en cas d’erreur.")
    if message := st.session_state.pop("finops_flash", None):
        st.success(message)
    selected = _resource_controls(mode, rows)
    st.caption(f"Du {start:%d/%m/%Y} au {end:%d/%m/%Y} inclus · UTC")
    try:
        finops.validate_period(start, end)
    except ValueError as exc:
        st.warning(str(exc))
        return
    if mode == "live" and start.year < today.year:
        st.info("Historique ancien : la disponibilité dépend de la rétention Databricks et des archives raccordées. Une année sans données ne signifie pas un coût nul.")
    if not selected:
        st.info("Sélectionnez au moins une ressource.")
        return
    usage_table = str(_setting("FINOPS_USAGE_TABLE", "system.billing.usage"))
    history_table = str(_setting("FINOPS_QUERY_HISTORY_TABLE", "system.query.history"))
    key = (user["email"], mode, start, end, usage_table, history_table,
           tuple((row["id"], row["kind"], row["external_id"]) for row in selected))
    if st.session_state.get("finops_v2_snapshot", {}).get("key") != key:
        st.session_state.pop("finops_v2_snapshot", None)
    refresh = st.button("Actualiser les consommations", key="finops_refresh", type="primary")
    if refresh or (mode == "demo" and "finops_v2_snapshot" not in st.session_state):
        results = {}
        with st.spinner("Chargement des consommations…"):
            for resource in selected:
                try:
                    frame = finops.load_resource_usage(resource, start, end, mode, usage_table, history_table)
                    results[resource["id"]] = dict(frame=frame)
                except (finops.MonitoringUnavailable, ValueError, PermissionError) as exc:
                    results[resource["id"]] = dict(error=str(exc))
        st.session_state.finops_v2_snapshot = dict(key=key, results=results, loaded_at=datetime.now(timezone.utc))
    snapshot = st.session_state.get("finops_v2_snapshot")
    if mode == "live" and snapshot:
        try:
            finops.authorize_monitoring(real=True)
        except (PermissionError, finops.MonitoringUnavailable) as exc:
            st.session_state.pop("finops_v2_snapshot", None)
            st.warning(str(exc))
            return
    if snapshot:
        st.caption(f"Dernier chargement : {snapshot['loaded_at']:%d/%m/%Y à %H:%M} UTC")
        _display_results(selected, snapshot, mode, start, end)
    else:
        st.info("Actualisez pour lire les consommations Databricks de la période.")
    with st.expander("Sources et méthode de calcul"):
        st.write("Serveur : consommation en DBU, tarif initial de 1 €/DBU. Compute : durée cumulée d’exécution en secondes, valorisée à 0,90 €/h par défaut. Le tarif modifié s’applique à l’ensemble de la période consultée.")
        st.caption("La valorisation des secondes suit votre règle de calcul ; elle ne reconstitue pas la facture Databricks (temps d’inactivité, requêtes simultanées, autres frais). Les données réelles sont publiées avec un délai et peuvent être corrigées.")
        if mode == "demo":
            st.write("Le serveur de référence reprend 16 jours visibles entre le 26/09 et le 14/10/2026. Les totaux compute des 12 comptes anonymisés sont répartis sur une fenêtre fictive du 08 au 14/10/2026. Les autres dates, les années antérieures et les ressources ajoutées sont simulées.")
        st.caption("Les suivis sont conservés localement sur l’instance. Leur sauvegarde durable après redéploiement reste à prévoir avec la DSI.")
