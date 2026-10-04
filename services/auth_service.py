
import streamlit as st
import logging

from services.administration_fallback import (
    activate_local_mode,
    is_local_mode,
    reset_for_identity,
)


# ============================================================
# PROFILS AUTORISES
# ============================================================

from services.access_service import PROFILS


# ============================================================
# UTILISATEUR CONNECTE A DATABRICKS
# ============================================================

def get_connected_email() -> str | None:
    """
    Récupère l'adresse email de l'utilisateur authentifié
    par Databricks Apps.

    En local, cet en-tête n'est généralement pas disponible.
    """

    email = st.context.headers.get(
        "X-Forwarded-Email"
    )

    if not email:
        return None

    return email.strip().lower() or None


# ============================================================
# UTILISATEUR ENROB'EAU
# ============================================================

def get_current_user() -> dict | None:
    """
    Récupère les informations de l'utilisateur connecté
    dans la table Administration.

    Retourne None si l'email est absent ou inconnu.
    """

    email = get_connected_email()
    reset_for_identity(email)

    if not email:
        return None

    from services.administration_service import (
        DuplicateUserError,
        get_user_by_email,
    )

    if is_local_mode():
        return get_user_by_email(email)

    try:
        return get_user_by_email(email)
    except DuplicateUserError:
        raise
    except Exception:
        logging.getLogger(__name__).exception(
            "Échec de récupération du profil Databricks ; activation du secours local."
        )
        activate_local_mode(email)
        return get_user_by_email(email)


# ============================================================
# VERIFICATION DES DROITS
# ============================================================

def require_admin() -> dict:
    """
    Vérifie que l'utilisateur connecté est un
    administrateur actif.

    À utiliser avant toute opération sensible.
    """

    user = get_current_user()

    if (
        user is None
        or user["actif"] is not True
        or user["profil"] != "administrateur"
    ):
        raise PermissionError(
            "Accès réservé aux administrateurs."
        )

    return user
