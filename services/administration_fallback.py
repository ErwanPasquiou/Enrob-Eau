"""Stockage temporaire de secours, isolé de la table Databricks."""

from contextlib import closing, contextmanager
from pathlib import Path
import sqlite3

import streamlit as st


DATABASE_PATH = Path(__file__).resolve().parents[1] / "data/exemples/administration.sqlite3"
SESSION_KEY = "administration_local_email"


def is_local_mode() -> bool:
    return bool(st.session_state.get(SESSION_KEY))


def activate_local_mode(email: str) -> None:
    st.session_state[SESSION_KEY] = email


def reset_for_identity(email: str | None) -> None:
    if st.session_state.get(SESSION_KEY) != email:
        st.session_state.pop(SESSION_KEY, None)


class LocalConnection:
    """Même protocole de curseur que le connecteur SQL Databricks."""

    def __init__(self, connection):
        self.connection = connection

    def cursor(self):
        return closing(self.connection.cursor())


@contextmanager
def get_local_connection():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(DATABASE_PATH, timeout=30)) as connection:
        # Initialisation atomique ; ne pas recréer un compte supprimé.
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'administration'"
            ).fetchone()
            if not exists:
                connection.execute("""
                    CREATE TABLE administration (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nom TEXT NOT NULL,
                        prenom TEXT NOT NULL,
                        email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                        profil TEXT NOT NULL,
                        actif INTEGER NOT NULL DEFAULT 1 CHECK (actif IN (0, 1)),
                        date_creation TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                connection.execute("""
                    INSERT INTO administration (nom, prenom, email, profil, actif)
                    VALUES (?, ?, ?, ?, ?)
                """, ("Pasquiou", "Erwan", "erwan.pasquiou@saur.com", "administrateur", True))
        try:
            with connection:
                yield LocalConnection(connection)
        except sqlite3.IntegrityError as exc:
            raise ValueError("Données invalides ou adresse email déjà utilisée.") from exc
