import os
import re

import pandas as pd
import databricks.sql as dbsql

from databricks.sdk.core import Config


from services.access_service import PROFILS as PROFILS_AUTORISES
from services.administration_fallback import get_local_connection, is_local_mode


class DuplicateUserError(RuntimeError):
    """Une identité ambiguë doit rester refusée, même en cas de secours."""


def _get_table_name() -> str:
    """
    Récupère et sécurise le nom de la table injecté par Databricks Apps.
    Exemple attendu :
    tmo_dev.default.enrobeau_administration
    """

    if is_local_mode():
        return "administration"

    table_name = os.getenv("ADMINISTRATION_TABLE")

    if not table_name:
        raise RuntimeError(
            "La variable ADMINISTRATION_TABLE n'est pas définie."
        )

    pattern = r"^[A-Za-z0-9_]+\.[A-Za-z0-9_]+\.[A-Za-z0-9_]+$"

    if not re.fullmatch(pattern, table_name):
        raise RuntimeError(
            f"Nom de table invalide : {table_name}"
        )

    catalog, schema, table = table_name.split(".")

    return f"`{catalog}`.`{schema}`.`{table}`"


def get_connection():
    """
    Crée une connexion au SQL Warehouse avec
    l'identité du service principal de l'application.
    """

    if is_local_mode():
        return get_local_connection()

    warehouse_id = os.getenv("DATABRICKS_WAREHOUSE_ID")

    if not warehouse_id:
        raise RuntimeError(
            "La variable DATABRICKS_WAREHOUSE_ID n'est pas définie."
        )

    cfg = Config()

    server_hostname = cfg.host

    if server_hostname.startswith("https://"):
        server_hostname = server_hostname.replace("https://", "")
    elif server_hostname.startswith("http://"):
        server_hostname = server_hostname.replace("http://", "")

    server_hostname = server_hostname.rstrip("/")

    http_path = f"/sql/1.0/warehouses/{warehouse_id}"

    return dbsql.connect(
        server_hostname=server_hostname,
        http_path=http_path,
        credentials_provider=lambda: cfg.authenticate,
        _use_arrow_native_complex_types=False,
    )


# -------------------------------------------------------------------
# READ
# -------------------------------------------------------------------

def get_administration_users() -> pd.DataFrame:
    """
    Retourne l'ensemble des utilisateurs.
    """

    table_name = _get_table_name()

    query = f"""
        SELECT
            id,
            nom,
            prenom,
            email,
            profil,
            actif,
            date_creation
        FROM {table_name}
        ORDER BY
            actif DESC,
            nom ASC,
            prenom ASC
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)

            rows = cursor.fetchall()

            columns = [
                column[0]
                for column in cursor.description
            ]

    result = pd.DataFrame(rows, columns=columns)
    result["actif"] = result["actif"].astype(bool)
    return result


def get_user_by_id(user_id: int):
    """
    Retourne un utilisateur à partir de son identifiant.
    """

    table_name = _get_table_name()

    query = f"""
        SELECT
            id,
            nom,
            prenom,
            email,
            profil,
            actif,
            date_creation
        FROM {table_name}
        WHERE id = ?
        LIMIT 1
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                [user_id],
            )

            row = cursor.fetchone()

            if row is None:
                return None

            columns = [
                column[0]
                for column in cursor.description
            ]

    result = dict(zip(columns, row))
    result["actif"] = bool(result["actif"])
    return result


def email_exists(
    email: str,
    exclude_user_id: int | None = None,
) -> bool:
    """
    Vérifie si une adresse email existe déjà.
    """

    table_name = _get_table_name()

    email = email.strip().lower()

    if exclude_user_id is None:
        query = f"""
            SELECT COUNT(*)
            FROM {table_name}
            WHERE LOWER(email) = ?
        """

        parameters = [email]

    else:
        query = f"""
            SELECT COUNT(*)
            FROM {table_name}
            WHERE LOWER(email) = ?
              AND id <> ?
        """

        parameters = [
            email,
            exclude_user_id,
        ]

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                parameters,
            )

            count = cursor.fetchone()[0]

    return count > 0


# -------------------------------------------------------------------
# CREATE
# -------------------------------------------------------------------

def create_user(
    nom: str,
    prenom: str,
    email: str,
    profil: str,
    actif: bool = True,
):
    """
    Crée un utilisateur.
    """

    table_name = _get_table_name()

    nom = nom.strip()
    prenom = prenom.strip()
    email = email.strip().lower()
    profil = profil.strip().lower()

    if not nom:
        raise ValueError("Le nom est obligatoire.")

    if not prenom:
        raise ValueError("Le prénom est obligatoire.")

    if not email:
        raise ValueError("L'adresse email est obligatoire.")

    if profil not in PROFILS_AUTORISES:
        raise ValueError("Le profil sélectionné est invalide.")

    if email_exists(email):
        raise ValueError(
            "Un utilisateur avec cette adresse email existe déjà."
        )

    query = f"""
        INSERT INTO {table_name}
        (
            nom,
            prenom,
            email,
            profil,
            actif
        )
        VALUES (?, ?, ?, ?, ?)
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                [
                    nom,
                    prenom,
                    email,
                    profil,
                    actif,
                ],
            )


# -------------------------------------------------------------------
# UPDATE
# -------------------------------------------------------------------

def update_user(
    user_id: int,
    nom: str,
    prenom: str,
    email: str,
    profil: str,
    actif: bool,
):
    """
    Modifie un utilisateur existant.
    """

    table_name = _get_table_name()

    nom = nom.strip()
    prenom = prenom.strip()
    email = email.strip().lower()
    profil = profil.strip().lower()

    if not nom:
        raise ValueError("Le nom est obligatoire.")

    if not prenom:
        raise ValueError("Le prénom est obligatoire.")

    if not email:
        raise ValueError("L'adresse email est obligatoire.")

    if profil not in PROFILS_AUTORISES:
        raise ValueError("Le profil sélectionné est invalide.")

    if email_exists(
        email=email,
        exclude_user_id=user_id,
    ):
        raise ValueError(
            "Cette adresse email est déjà utilisée par un autre utilisateur."
        )

    query = f"""
        UPDATE {table_name}
        SET
            nom = ?,
            prenom = ?,
            email = ?,
            profil = ?,
            actif = ?
        WHERE id = ?
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                [
                    nom,
                    prenom,
                    email,
                    profil,
                    actif,
                    user_id,
                ],
            )


def set_user_active(
    user_id: int,
    actif: bool,
):
    """
    Active ou désactive rapidement un utilisateur.
    """

    table_name = _get_table_name()

    query = f"""
        UPDATE {table_name}
        SET actif = ?
        WHERE id = ?
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                [
                    actif,
                    user_id,
                ],
            )


# -------------------------------------------------------------------
# DELETE
# -------------------------------------------------------------------

def delete_user(user_id: int):
    """
    Supprime définitivement un utilisateur.
    À utiliser uniquement après confirmation explicite dans l'UI.
    """

    table_name = _get_table_name()

    query = f"""
        DELETE FROM {table_name}
        WHERE id = ?
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                [user_id],
            )


# ============================================================
# RECHERCHE UTILISATEUR PAR EMAIL
# ============================================================

def get_user_by_email(email: str) -> dict | None:
    """
    Recherche un utilisateur à partir de son email.

    Retourne ses informations si une seule correspondance
    existe, sinon None.

    Refuse les emails présents plusieurs fois.
    """

    if not email or not email.strip():
        return None

    table_name = _get_table_name()

    query = f"""
        SELECT
            id,
            nom,
            prenom,
            email,
            profil,
            actif,
            date_creation

        FROM {table_name}

        WHERE LOWER(TRIM(email)) = ?

        LIMIT 2
    """

    with get_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                query,
                [email.strip().lower()],
            )

            rows = cursor.fetchall()

            if not rows:
                return None

            if len(rows) > 1:
                raise DuplicateUserError(
                    "Plusieurs comptes correspondent à cet email."
                )

            columns = [
                column[0]
                for column in cursor.description
            ]

    result = dict(zip(columns, rows[0]))
    result["actif"] = bool(result["actif"])
    return result
