
import re

import streamlit as st

from components.header import render_header
from components.page_content import create_page_content

from services.administration_service import (
    PROFILS_AUTORISES,
    create_user,
    delete_user,
    get_administration_users,
    set_user_active,
    update_user,
)


# ============================================================
# CONFIGURATION UI
# ============================================================

PROFIL_LABELS = {
    "agent": "Agent",
    "ordonnanceur": "Ordonnanceur",
    "agent externe": "Agent externe",
    "administrateur": "Administrateur",
}


# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def profil_label(profil: str) -> str:
    """
    Retourne le libellé du profil.
    """

    return PROFIL_LABELS.get(
        profil,
        profil.capitalize(),
    )


def email_valide(email: str) -> bool:
    """
    Validation simple de l'adresse email.
    """

    pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

    return bool(
        re.fullmatch(
            pattern,
            email.strip(),
        )
    )


# ============================================================
# MISE EN ATTENTE D'UNE OPERATION
# ============================================================

def queue_admin_action(
    action: str,
    data: dict,
):
    """
    Enregistre une opération à effectuer au prochain
    cycle d'exécution de la page Administration.

    Cela permet de traiter l'opération avant de
    reconstruire l'interface.
    """

    st.session_state["admin_pending_action"] = {
        "action": action,
        "data": data,
    }

    st.rerun()


# ============================================================
# EXECUTION DES OPERATIONS CRUD
# ============================================================

def execute_admin_action(
    pending: dict,
) -> str:
    """
    Exécute l'opération enregistrée dans la session.

    Retourne un message de confirmation.
    """

    action = pending["action"]

    data = pending["data"]


    # --------------------------------------------------------
    # CREATE
    # --------------------------------------------------------

    if action == "create":

        create_user(
            nom=data["nom"],
            prenom=data["prenom"],
            email=data["email"],
            profil=data["profil"],
            actif=data["actif"],
        )

        return "Utilisateur créé avec succès."


    # --------------------------------------------------------
    # UPDATE
    # --------------------------------------------------------

    elif action == "update":

        update_user(
            user_id=data["user_id"],
            nom=data["nom"],
            prenom=data["prenom"],
            email=data["email"],
            profil=data["profil"],
            actif=data["actif"],
        )

        return "Modifications enregistrées avec succès."


    # --------------------------------------------------------
    # ACTIVATION / DESACTIVATION
    # --------------------------------------------------------

    elif action == "toggle_active":

        set_user_active(
            user_id=data["user_id"],
            actif=data["actif"],
        )

        return "Statut de l'utilisateur mis à jour."


    # --------------------------------------------------------
    # DELETE
    # --------------------------------------------------------

    elif action == "delete":

        delete_user(
            user_id=data["user_id"],
        )

        return "Utilisateur supprimé avec succès."


    # --------------------------------------------------------
    # ACTION INCONNUE
    # --------------------------------------------------------

    else:

        raise ValueError(
            f"Opération inconnue : {action}"
        )


# ============================================================
# VERIFICATION DES DROITS
# ============================================================

user = st.session_state.get(
    "current_user"
)

if (
    not user
    or not user.get("actif")
    or user.get("profil") != "administrateur"
):

    st.error(
        "Accès réservé aux administrateurs d'Enrob'Eau."
    )

    st.stop()


# ============================================================
# INFORMATIONS UTILISATEUR
# ============================================================

prenom_connecte = str(
    user.get("prenom") or ""
).strip()

nom_connecte = str(
    user.get("nom") or ""
).strip()

initiales = (
    f"{prenom_connecte[:1]}"
    f"{nom_connecte[:1]}"
).upper()


# ============================================================
# RECUPERATION DE L'OPERATION EN ATTENTE
# ============================================================

# L'opération est retirée de la session AVANT son exécution
# afin d'éviter qu'elle soit automatiquement rejouée
# lors d'un éventuel nouveau rerun.

pending = st.session_state.pop(
    "admin_pending_action",
    None,
)


# ============================================================
# EXECUTION DE L'OPERATION EN ATTENTE
# ============================================================

operation_message = None

if pending:

    try:

        operation_message = execute_admin_action(
            pending
        )

    except ValueError as e:

        st.warning(
            str(e)
        )

        st.stop()

    except Exception:

        st.error(
            "Une erreur est survenue pendant "
            "l'enregistrement des données."
        )

        st.info(
            "Veuillez vérifier l'état de la table "
            "Administration avant de réessayer."
        )

        st.stop()


# ============================================================
# CHARGEMENT DES UTILISATEURS
# ============================================================

# Cette lecture est réalisée après l'éventuelle opération
# CRUD, afin de récupérer les données actualisées.

try:

    utilisateurs = get_administration_users()

except Exception:

    if operation_message:

        st.warning(
            "L'opération a été exécutée, mais la liste "
            "des utilisateurs n'a pas pu être actualisée."
        )

        st.info(
            "Actualisez la page pour vérifier les données."
        )

    else:

        st.error(
            "Impossible de récupérer les utilisateurs."
        )

        st.info(
            "Veuillez réessayer dans quelques instants."
        )

    st.stop()


# ============================================================
# HEADER
# ============================================================

render_header(
    active_page="Administration",
    initials=initiales,
    show_admin=True,
)


# ============================================================
# CONTENU PRINCIPAL
# ============================================================

content = create_page_content()


with content:

    left, center, right = st.columns(
        [1, 18, 1]
    )

    with center:

        # ====================================================
        # TITRE
        # ====================================================

        st.title(
            "Administration"
        )

        st.caption(
            "Gestion des utilisateurs et des droits "
            "d'accès à Enrob'Eau."
        )


        # ====================================================
        # MESSAGE DE CONFIRMATION
        # ====================================================

        if operation_message:

            st.success(
                operation_message
            )


        # ====================================================
        # INDICATEURS
        # ====================================================

        total_utilisateurs = len(
            utilisateurs
        )

        if total_utilisateurs > 0:

            utilisateurs_actifs = int(
                utilisateurs["actif"]
                .fillna(False)
                .astype(bool)
                .sum()
            )

            administrateurs = int(
                (
                    utilisateurs["profil"]
                    == "administrateur"
                ).sum()
            )

        else:

            utilisateurs_actifs = 0

            administrateurs = 0


        col_total, col_actifs, col_admins = st.columns(
            3
        )


        with col_total:

            st.metric(
                "Utilisateurs",
                total_utilisateurs,
            )


        with col_actifs:

            st.metric(
                "Actifs",
                utilisateurs_actifs,
            )


        with col_admins:

            st.metric(
                "Administrateurs",
                administrateurs,
            )


        st.divider()


        # ====================================================
        # ONGLETS
        # ====================================================

        tab_users, tab_add, tab_edit = st.tabs(
            [
                "Utilisateurs",
                "Ajouter",
                "Modifier",
            ]
        )


        # ====================================================
        # ONGLET 1 : UTILISATEURS
        # ====================================================

        with tab_users:

            st.subheader(
                "Gestion des utilisateurs"
            )

            st.caption(
                "Recherchez, filtrez et consultez les "
                "utilisateurs autorisés à accéder "
                "à Enrob'Eau."
            )


            # ------------------------------------------------
            # FILTRES
            # ------------------------------------------------

            filter_search, filter_profil, filter_status = (
                st.columns([2, 1, 1])
            )


            with filter_search:

                recherche = st.text_input(
                    "Rechercher",
                    placeholder=(
                        "Nom, prénom ou adresse email..."
                    ),
                    key="admin_search",
                )


            with filter_profil:

                profil_filtre = st.selectbox(
                    "Profil",
                    [
                        "Tous",
                        "Agent",
                        "Ordonnanceur",
                        "Agent externe",
                        "Administrateur",
                    ],
                    key="admin_filter_profile",
                )


            with filter_status:

                statut_filtre = st.selectbox(
                    "État",
                    [
                        "Tous",
                        "Actifs",
                        "Inactifs",
                    ],
                    key="admin_filter_status",
                )


            # ------------------------------------------------
            # FILTRAGE
            # ------------------------------------------------

            resultat = utilisateurs.copy()


            if recherche:

                recherche_normalisee = (
                    recherche.strip().lower()
                )

                masque = (
                    resultat["nom"]
                    .fillna("")
                    .astype(str)
                    .str.lower()
                    .str.contains(
                        recherche_normalisee,
                        regex=False,
                    )
                    |
                    resultat["prenom"]
                    .fillna("")
                    .astype(str)
                    .str.lower()
                    .str.contains(
                        recherche_normalisee,
                        regex=False,
                    )
                    |
                    resultat["email"]
                    .fillna("")
                    .astype(str)
                    .str.lower()
                    .str.contains(
                        recherche_normalisee,
                        regex=False,
                    )
                )

                resultat = resultat[
                    masque
                ]


            if profil_filtre != "Tous":

                profil_db = (
                    profil_filtre.lower()
                )

                resultat = resultat[
                    resultat["profil"] == profil_db
                ]


            if statut_filtre == "Actifs":

                resultat = resultat[
                    resultat["actif"] == True
                ]


            elif statut_filtre == "Inactifs":

                resultat = resultat[
                    resultat["actif"] == False
                ]


            # ------------------------------------------------
            # AFFICHAGE DU TABLEAU
            # ------------------------------------------------

            if resultat.empty:

                st.info(
                    "Aucun utilisateur ne correspond "
                    "aux critères sélectionnés."
                )

            else:

                affichage = resultat.copy()


                # Nom complet

                affichage["Utilisateur"] = (
                    affichage["prenom"].fillna("")
                    + " "
                    + affichage["nom"].fillna("")
                )


                # Profil

                affichage["Profil"] = (
                    affichage["profil"]
                    .map(PROFIL_LABELS)
                    .fillna(
                        affichage["profil"]
                    )
                )


                # Statut

                affichage["État"] = (
                    affichage["actif"].apply(
                        lambda actif:
                            "Actif"
                            if actif
                            else "Inactif"
                    )
                )


                # Colonnes affichées

                affichage = affichage[
                    [
                        "Utilisateur",
                        "email",
                        "Profil",
                        "État",
                        "date_creation",
                    ]
                ]


                affichage = affichage.rename(
                    columns={
                        "email": "Email",
                        "date_creation": "Créé le",
                    }
                )


                st.dataframe(
                    affichage,
                    use_container_width=True,
                    hide_index=True,
                )


                st.caption(
                    f"{len(resultat)} utilisateur(s) affiché(s)."
                )


            st.divider()


            # =================================================
            # ACTIVATION RAPIDE
            # =================================================

            if not utilisateurs.empty:

                st.subheader(
                    "Activation rapide"
                )


                options_activation = {

                    int(row["id"]):
                        (
                            f"{row['prenom']} "
                            f"{row['nom']} — "
                            f"{row['email']}"
                        )

                    for _, row in utilisateurs.iterrows()
                }


                activation_id = st.selectbox(
                    "Utilisateur",
                    options=list(
                        options_activation.keys()
                    ),
                    format_func=lambda user_id:
                        options_activation[user_id],
                    key="activation_user",
                )


                utilisateur_activation = (
                    utilisateurs[
                        utilisateurs["id"]
                        == activation_id
                    ].iloc[0]
                )


                actif_actuel = bool(
                    utilisateur_activation["actif"]
                )


                col_status, col_action = st.columns(
                    [3, 1]
                )


                with col_status:

                    if actif_actuel:

                        st.success(
                            "Cet utilisateur est "
                            "actuellement actif."
                        )

                    else:

                        st.warning(
                            "Cet utilisateur est "
                            "actuellement inactif."
                        )


                with col_action:

                    texte_action = (
                        "Désactiver"
                        if actif_actuel
                        else "Activer"
                    )


                    if st.button(
                        texte_action,
                        use_container_width=True,
                        key="toggle_activation",
                    ):

                        queue_admin_action(
                            action="toggle_active",
                            data={
                                "user_id": int(
                                    activation_id
                                ),
                                "actif": not actif_actuel,
                            },
                        )


        # ====================================================
        # ONGLET 2 : AJOUTER
        # ====================================================

        with tab_add:

            st.subheader(
                "Ajouter un utilisateur"
            )

            st.caption(
                "Créez un nouvel utilisateur "
                "autorisé à accéder à Enrob'Eau."
            )


            with st.form(
                "create_user_form",
                clear_on_submit=True,
            ):

                create_col1, create_col2 = st.columns(
                    2
                )


                with create_col1:

                    nom = st.text_input(
                        "Nom *",
                        placeholder="Ex. Dupont",
                    )


                with create_col2:

                    prenom = st.text_input(
                        "Prénom *",
                        placeholder="Ex. Marie",
                    )


                email = st.text_input(
                    "Adresse email *",
                    placeholder=(
                        "prenom.nom@entreprise.com"
                    ),
                )


                profil = st.selectbox(
                    "Profil *",
                    options=PROFILS_AUTORISES,
                    format_func=profil_label,
                )


                actif = st.checkbox(
                    "Utilisateur actif",
                    value=True,
                )


                st.caption(
                    "* Champs obligatoires"
                )


                submit_create = st.form_submit_button(
                    "Créer l'utilisateur",
                    use_container_width=True,
                )


            # =================================================
            # VALIDATION DU FORMULAIRE DE CREATION
            # =================================================

            if submit_create:

                erreurs = []


                if not nom.strip():

                    erreurs.append(
                        "Le nom est obligatoire."
                    )


                if not prenom.strip():

                    erreurs.append(
                        "Le prénom est obligatoire."
                    )


                if not email.strip():

                    erreurs.append(
                        "L'adresse email est obligatoire."
                    )


                elif not email_valide(email):

                    erreurs.append(
                        "L'adresse email n'est pas valide."
                    )


                # ---------------------------------------------
                # AFFICHAGE DES ERREURS
                # ---------------------------------------------

                if erreurs:

                    for erreur in erreurs:

                        st.error(
                            erreur
                        )


                # ---------------------------------------------
                # MISE EN ATTENTE DE LA CREATION
                # ---------------------------------------------

                else:

                    queue_admin_action(
                        action="create",
                        data={
                            "nom": nom.strip(),
                            "prenom": prenom.strip(),
                            "email": email.strip().lower(),
                            "profil": profil,
                            "actif": actif,
                        },
                    )


        # ====================================================
        # ONGLET 3 : MODIFIER
        # ====================================================

        with tab_edit:

            st.subheader(
                "Modifier un utilisateur"
            )


            if utilisateurs.empty:

                st.info(
                    "Aucun utilisateur n'est disponible."
                )


            else:

                # ------------------------------------------------
                # LISTE DES UTILISATEURS
                # ------------------------------------------------

                options = {

                    int(row["id"]):
                        (
                            f"{row['prenom']} "
                            f"{row['nom']} — "
                            f"{row['email']}"
                        )

                    for _, row in utilisateurs.iterrows()
                }


                selected_user_id = st.selectbox(
                    "Sélectionner un utilisateur",
                    options=list(
                        options.keys()
                    ),
                    format_func=lambda user_id:
                        options[user_id],
                    key="edit_user_select",
                )


                # ------------------------------------------------
                # RECUPERATION DE L'UTILISATEUR SELECTIONNE
                # ------------------------------------------------

                # Réutilisation des données déjà chargées.
                # Pas de nouvelle requête Databricks.

                utilisateur_filtre = utilisateurs.loc[
                    utilisateurs["id"]
                    == selected_user_id
                ]


                if utilisateur_filtre.empty:

                    utilisateur = None

                else:

                    utilisateur = (
                        utilisateur_filtre.iloc[0].to_dict()
                    )


                # =================================================
                # FORMULAIRE DE MODIFICATION
                # =================================================

                if utilisateur:

                    st.divider()


                    with st.form(
                        f"edit_user_form_{selected_user_id}"
                    ):

                        edit_col1, edit_col2 = st.columns(
                            2
                        )


                        with edit_col1:

                            edit_nom = st.text_input(
                                "Nom *",
                                value=utilisateur["nom"],
                            )


                        with edit_col2:

                            edit_prenom = st.text_input(
                                "Prénom *",
                                value=utilisateur["prenom"],
                            )


                        edit_email = st.text_input(
                            "Adresse email *",
                            value=utilisateur["email"],
                        )


                        profil_index = list(
                            PROFILS_AUTORISES
                        ).index(
                            utilisateur["profil"]
                        )


                        edit_profil = st.selectbox(
                            "Profil *",
                            options=PROFILS_AUTORISES,
                            index=profil_index,
                            format_func=profil_label,
                        )


                        edit_actif = st.checkbox(
                            "Utilisateur actif",
                            value=bool(
                                utilisateur["actif"]
                            ),
                        )


                        submit_update = (
                            st.form_submit_button(
                                "Enregistrer les modifications",
                                use_container_width=True,
                            )
                        )


                    # =============================================
                    # VALIDATION DU FORMULAIRE DE MODIFICATION
                    # =============================================

                    if submit_update:

                        erreurs = []


                        if not edit_nom.strip():

                            erreurs.append(
                                "Le nom est obligatoire."
                            )


                        if not edit_prenom.strip():

                            erreurs.append(
                                "Le prénom est obligatoire."
                            )


                        if not edit_email.strip():

                            erreurs.append(
                                "L'adresse email est obligatoire."
                            )


                        elif not email_valide(
                            edit_email
                        ):

                            erreurs.append(
                                "L'adresse email n'est pas valide."
                            )


                        # -----------------------------------------
                        # AFFICHAGE DES ERREURS
                        # -----------------------------------------

                        if erreurs:

                            for erreur in erreurs:

                                st.error(
                                    erreur
                                )


                        # -----------------------------------------
                        # MISE EN ATTENTE DE LA MODIFICATION
                        # -----------------------------------------

                        else:

                            queue_admin_action(
                                action="update",
                                data={
                                    "user_id": int(
                                        selected_user_id
                                    ),
                                    "nom": edit_nom.strip(),
                                    "prenom": edit_prenom.strip(),
                                    "email": edit_email.strip().lower(),
                                    "profil": edit_profil,
                                    "actif": edit_actif,
                                },
                            )


                    # =================================================
                    # SUPPRESSION D'UN UTILISATEUR
                    # =================================================

                    st.divider()

                    st.subheader(
                        "Zone sensible"
                    )

                    st.warning(
                        "La suppression est définitive. "
                        "Dans la majorité des cas, "
                        "privilégiez la désactivation "
                        "du compte."
                    )


                    # ------------------------------------------------
                    # CONFIRMATION DE LA SUPPRESSION
                    # ------------------------------------------------

                    confirmation = st.checkbox(
                        (
                            "Je confirme vouloir supprimer "
                            "définitivement "
                            f"{utilisateur['prenom']} "
                            f"{utilisateur['nom']}."
                        ),
                        key=(
                            f"confirm_delete_"
                            f"{selected_user_id}"
                        ),
                    )


                    # ------------------------------------------------
                    # BOUTON SUPPRESSION
                    # ------------------------------------------------

                    if st.button(
                        "Supprimer définitivement",
                        disabled=not confirmation,
                        use_container_width=True,
                        key=(
                            f"delete_user_"
                            f"{selected_user_id}"
                        ),
                    ):

                        queue_admin_action(
                            action="delete",
                            data={
                                "user_id": int(
                                    selected_user_id
                                ),
                            },
                        )
