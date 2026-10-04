from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from services import administration_fallback as fallback
from services import administration_service as admin
from services import auth_service as auth


EMAIL = "erwan.pasquiou@saur.com"
ROOT = Path(__file__).resolve().parents[1]


class AdministrationFallbackTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.state = {}
        for patcher in (
            patch.object(fallback, "DATABASE_PATH", Path(temporary.name) / "admin.sqlite3"),
            patch.object(fallback.st, "session_state", self.state),
            patch.object(auth, "get_connected_email", return_value=EMAIL),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_seed_crud_and_persistence_without_databricks(self):
        fallback.activate_local_mode(EMAIL)
        with patch.object(admin.dbsql, "connect", side_effect=AssertionError("Databricks interdit")):
            users = admin.get_administration_users()
            self.assertEqual(len(users), 1)
            self.assertEqual(users.iloc[0]["email"], EMAIL)
            self.assertEqual(auth.require_admin()["profil"], "administrateur")
            admin.create_user(" Test ", " Agent ", " AGENT@example.test ", "agent")
            user = admin.get_user_by_email("agent@example.test")
            self.assertEqual(user["nom"], "Test")
            self.assertIs(user["actif"], True)
            self.assertTrue(user["date_creation"])
            with self.assertRaises(ValueError):
                admin.create_user("Test", "Agent", "AGENT@example.test", "agent")
            with self.assertRaises(ValueError):
                admin.create_user("", "Agent", "invalid@example.test", "agent")
            with self.assertRaises(ValueError):
                admin.update_user(user["id"], "Test", "Agent", EMAIL, "agent", True)
            with self.assertRaises(ValueError):
                admin.update_user(user["id"], "Test", "Agent", user["email"], "invalide", True)
            admin.update_user(user["id"], "Modifié", "Agent", user["email"], "agent externe", True)
            admin.set_user_active(user["id"], False)
            self.assertIs(admin.get_user_by_id(user["id"])["actif"], False)
            self.assertEqual(admin.get_user_by_id(user["id"])["profil"], "agent externe")
            self.assertFalse(admin.email_exists(user["email"], exclude_user_id=user["id"]))
            self.state.clear()
            fallback.activate_local_mode(EMAIL)
            self.assertEqual(len(admin.get_administration_users()), 2)
            admin.delete_user(user["id"])
            self.assertIsNone(admin.get_user_by_id(user["id"]))
            admin.delete_user(int(users.iloc[0]["id"]))
            self.assertTrue(admin.get_administration_users().empty)
            self.assertIsNone(auth.get_current_user())

    def test_profile_failure_switches_and_stays_local(self):
        with patch.object(admin, "Config", side_effect=RuntimeError("Warehouse indisponible")) as config, patch.dict(
            "os.environ", {"ADMINISTRATION_TABLE": "catalog.schema.users", "DATABRICKS_WAREHOUSE_ID": "test"}
        ), self.assertLogs(auth.__name__, level="ERROR"):
            self.assertEqual(auth.get_current_user()["email"], EMAIL)
            self.assertEqual(auth.get_current_user()["email"], EMAIL)
            config.assert_called_once()
        self.assertTrue(fallback.is_local_mode())

    def test_success_unknown_and_invalid_profiles_do_not_switch(self):
        for user in (None, {"actif": False}, {"actif": True, "profil": "invalide"}):
            with patch.object(admin, "get_user_by_email", return_value=user):
                self.assertEqual(auth.get_current_user(), user)
                self.assertFalse(fallback.is_local_mode())

    def test_duplicate_identity_does_not_switch(self):
        with patch.object(admin, "get_user_by_email", side_effect=admin.DuplicateUserError("doublon")):
            with self.assertRaises(admin.DuplicateUserError):
                auth.get_current_user()
        self.assertFalse(fallback.is_local_mode())

    def test_identity_change_resets_mode_and_missing_identity_is_denied(self):
        fallback.activate_local_mode(EMAIL)
        with patch.object(auth, "get_connected_email", return_value=None), patch.object(admin, "get_user_by_email") as lookup:
            self.assertIsNone(auth.get_current_user())
            lookup.assert_not_called()
        self.assertFalse(fallback.is_local_mode())
        fallback.activate_local_mode(EMAIL)
        with patch.object(auth, "get_connected_email", return_value="other@example.test"), patch.object(admin, "get_user_by_email", return_value=None):
            self.assertIsNone(auth.get_current_user())
        self.assertFalse(fallback.is_local_mode())

    def test_unknown_local_identity_does_not_receive_seed_admin(self):
        with patch.object(auth, "get_connected_email", return_value="other@example.test"), patch.object(
            admin, "_get_table_name", side_effect=[RuntimeError("panne"), "administration"]
        ), self.assertLogs(auth.__name__, level="ERROR"):
            self.assertIsNone(auth.get_current_user())

    def test_disabled_local_admin_is_denied_without_reseeding(self):
        fallback.activate_local_mode(EMAIL)
        user = auth.require_admin()
        admin.set_user_active(user["id"], False)
        with self.assertRaises(PermissionError):
            auth.require_admin()

    def test_app_shows_warning_and_admin_navigation_on_fallback(self):
        with patch.object(admin, "Config", side_effect=RuntimeError("panne")), patch.dict(
            "os.environ", {"ADMINISTRATION_TABLE": "catalog.schema.users", "DATABRICKS_WAREHOUSE_ID": "test"}
        ), patch("streamlit.navigation") as navigation, self.assertLogs(auth.__name__, level="ERROR"):
            app = AppTest.from_file(str(ROOT / "app.py")).run(timeout=30)
        self.assertFalse(app.exception)
        self.assertTrue(any("Mode dégradé" in warning.value for warning in app.warning))
        self.assertIn("Administration", [page.title for page in navigation.call_args.args[0]])

    def test_administration_page_executes_local_pending_action(self):
        fallback.activate_local_mode(EMAIL)
        self.state["current_user"] = auth.require_admin()
        self.state["admin_pending_action"] = {
            "action": "create",
            "data": dict(nom="Test", prenom="Agent", email="ui@example.test", profil="agent", actif=True),
        }
        app = AppTest.from_file(str(ROOT / "pages/administration.py")).run(timeout=30)
        self.assertFalse(app.exception)
        self.assertTrue(app.success)
        self.assertIsNotNone(admin.get_user_by_email("ui@example.test"))


if __name__ == "__main__":
    unittest.main()
