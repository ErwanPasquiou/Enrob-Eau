"""Les images de test sont générées en mémoire et les tables dans un dossier temporaire."""
from contextlib import contextmanager
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from streamlit.testing.v1 import AppTest
from services import photo_service as photos
from services.business_data_service import load_store
from services.dossier_edit_service import new_record, save_record, delete_record


def image_bytes(color="red"):
    buffer = BytesIO()
    Image.new("RGB", (4, 4), color).save(buffer, format="PNG")
    return buffer.getvalue()


class PhotoTests(unittest.TestCase):
    def setUp(self):
        self.store = load_store()
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        for table, rows in self.store.items():
            (self.root / f"{table}.json").write_text(json.dumps(rows), encoding="utf-8")
        patcher = patch("services.business_data_service.DATA_DIR", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.request = self.store["demandes"][0]
        self.ref = self.request["RequestReference"]
        self.email = self.request["RequesterReference"]
        self.photo = photos.prepare_photo("image.png", image_bytes(), photo_name="Avant travaux")

    def test_both_tables_crud_and_lazy_queries(self):
        for table, reference in (("demandes", self.ref), ("prestations", self.store["prestations"][0]["ServiceReference"])):
            with self.subTest(table=table):
                photos.add_photos(table, reference, [self.photo], self.email)
                statements = []
                real_connection = photos.connection

                @contextmanager
                def traced():
                    with real_connection() as db:
                        db.set_trace_callback(statements.append)
                        yield db

                with patch.object(photos, "connection", traced):
                    rows = photos.list_photos(table, reference)
                self.assertNotIn("Content", rows[0])
                self.assertTrue(all("Content" not in sql for sql in statements))
                original = rows[0]
                self.assertEqual(photos.read_photo(table, reference, original["PhotoReference"]), self.photo["Content"])
                replacement = photos.prepare_photo("nouvelle.png", image_bytes("blue"), photo_name="Après travaux")
                photos.update_photo(table, reference, original, "Après travaux", replacement)
                updated = photos.list_photos(table, reference)[0]
                self.assertEqual(updated["Caption"], "Après travaux")
                self.assertEqual(photos.read_photo(table, reference, original["PhotoReference"]), replacement["Content"])
                with self.assertRaisesRegex(ValueError, "changé"):
                    photos.delete_photo(table, reference, original)
                photos.delete_photo(table, reference, updated)
                self.assertEqual(photos.list_photos(table, reference), [])

    def test_owner_and_parent_boundaries(self):
        photos.add_photos("demandes", self.ref, [self.photo], self.email, owner_email=self.email.upper())
        row = photos.list_photos("demandes", self.ref)[0]
        for operation in (
            lambda: photos.list_photos("demandes", self.ref, "other@example.test"),
            lambda: photos.read_photo("demandes", self.ref, row["PhotoReference"], "other@example.test"),
            lambda: photos.update_photo("demandes", self.ref, row, "Test", owner_email="other@example.test"),
            lambda: photos.delete_photo("demandes", self.ref, row, "other@example.test"),
            lambda: photos.add_photos("demandes", "missing", [self.photo], self.email),
            lambda: photos.read_photo("demandes", self.store["demandes"][1]["RequestReference"], row["PhotoReference"]),
            lambda: save_record("demandes", self.request, self.request, owner_email="other@example.test"),
        ):
            with self.assertRaises(ValueError):
                operation()

    def test_invalid_batch_and_parent_rollback(self):
        invalid = dict(self.photo, Content=b"not an image")
        with self.assertRaises(ValueError):
            photos.add_photos("demandes", self.ref, [self.photo, invalid], self.email)
        self.assertEqual(photos.list_photos("demandes", self.ref), [])
        row = new_record("demandes")
        row.update(RequestReason="Test", ReportedCity="Test", RequesterReference=self.email)
        with patch.object(photos, "add_photos", side_effect=OSError("Test")):
            with self.assertRaises(OSError):
                save_record("demandes", row, photos=[self.photo], actor=self.email)
        self.assertFalse(any(r["RequestReference"] == row["RequestReference"] for r in load_store()["demandes"]))
        saved = save_record("demandes", row, photos=[self.photo], actor=self.email, owner_email=self.email)
        self.assertEqual(len(photos.list_photos("demandes", saved["RequestReference"])), 1)

    def test_service_with_photos_cannot_be_deleted(self):
        service = self.store["prestations"][0]
        ref = service["ServiceReference"]
        photos.add_photos("prestations", ref, [self.photo], self.email)
        with self.assertRaisesRegex(ValueError, "photos"):
            delete_record("prestations", service)
        photos.delete_photo("prestations", ref, photos.list_photos("prestations", ref)[0])
        delete_record("prestations", service)

    def test_list_does_not_read_images_and_viewer_reads_only_selected_photo(self):
        photos.add_photos("demandes", self.ref, [self.photo], self.email)
        app = AppTest.from_string(f'from components.photos import render_photos\nrender_photos("demandes", "{self.ref}")')
        with patch.object(photos, "read_photo", wraps=photos.read_photo) as read:
            app.run(timeout=30)
            self.assertEqual(len(app.exception), 0)
            read.assert_not_called()
            self.assertFalse(any(b.label in {"Afficher", "Masquer les photos", "Consulter et gérer les photos"} for b in app.button))
            photo_id = photos.list_photos("demandes", self.ref)[0]["PhotoReference"]
            viewer = AppTest.from_string('from components.photo_viewer import render_photo_viewer\nrender_photo_viewer()')
            viewer.session_state["current_user"] = {"actif": True, "profil": "agent", "email": self.email}
            viewer.query_params.update(photo=photo_id, photo_table="demandes", photo_parent=self.ref, photo_scope="mine")
            viewer.run(timeout=30)
            self.assertEqual(len(viewer.exception), 0)
            read.assert_called_once_with("demandes", self.ref, photo_id, self.email)

    def test_four_successive_captures_and_required_names(self):
        from components.photos import append_uploads, prepare_uploads
        queue = []
        for index in range(4):
            upload = BytesIO(image_bytes())
            upload.name = "camera.jpg"
            append_uploads(queue, [upload])
            self.assertEqual(len(queue), index + 1)
            with self.assertRaisesRegex(ValueError, "nom"):
                prepare_uploads(queue)
            queue[-1]["PhotoName"] = f"Vue {index + 1}"
        photos.add_photos("demandes", self.ref, prepare_uploads(queue), self.email)
        self.assertEqual(len(photos.list_photos("demandes", self.ref)), 4)
        row = photos.list_photos("demandes", self.ref)[0]
        with self.assertRaisesRegex(ValueError, "obligatoire"):
            photos.update_photo("demandes", self.ref, row, "", photo_name="  ")

    def test_camera_resets_and_names_survive_source_changes(self):
        app = AppTest.from_string('from components.photos import render_upload_editor, refresh_uploads\nrender_upload_editor("capture_test")\nrefresh_uploads("capture_test")')
        app.run(timeout=30)
        app.radio[0].set_value("Appareil photo").run()
        for index in range(4):
            upload = BytesIO(image_bytes())
            upload.name = "camera.jpg"
            with patch("streamlit.camera_input", side_effect=[upload, None]):
                app.run(timeout=30)
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(len(app.text_input), index + 1)
            self.assertEqual(app.session_state["capture_test_revision"], index + 1)
            app.text_input[index].set_value(f"Vue {index + 1}").run()
        app.radio[0].set_value("Document / galerie").run()
        self.assertEqual([w.value for w in app.text_input], [f"Vue {i + 1}" for i in range(4)])
        app.button[0].click().run()
        self.assertEqual(len(app.text_input), 3)

    def test_viewer_rejects_other_owner_without_reading_content(self):
        photos.add_photos("demandes", self.ref, [self.photo], self.email)
        row = photos.list_photos("demandes", self.ref)[0]
        viewer = AppTest.from_string('from components.photo_viewer import render_photo_viewer\nrender_photo_viewer()')
        viewer.session_state["current_user"] = {"actif": True, "profil": "agent", "email": "other@example.test"}
        viewer.query_params.update(photo=row["PhotoReference"], photo_table="demandes", photo_parent=self.ref, photo_scope="mine")
        with patch.object(photos, "read_photo") as read:
            viewer.run(timeout=30)
            read.assert_not_called()
        self.assertEqual(len(viewer.error), 1)

    def test_staged_photos_save_and_clear_selection(self):
        app = AppTest.from_string(f'from components.photos import render_photos\nrender_photos("demandes", "{self.ref}")')
        prefix = f"photos_demandes_{self.ref}_add"
        app.session_state[f"{prefix}_queue"] = [dict(self.photo, DraftId="pending")]
        app.run(timeout=30)
        next(b for b in app.button if b.label == "Enregistrer les photos (1)").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(photos.list_photos("demandes", self.ref)), 1)
        self.assertEqual(app.session_state[f"{prefix}_queue"], [])

    def test_request_fields_survive_a_new_capture(self):
        app = AppTest.from_string('from components.dossier_forms import render_record_form\nrender_record_form("demandes", None, mobile=True)')
        app.session_state["current_user"] = {"actif": True, "email": self.email}
        app.run(timeout=30)
        field = next(w for w in app.text_input if w.key.endswith("_RequestReason"))
        field.set_value("Conserver ce motif").run()
        self.assertFalse(any(w.label == "Source des photos" for w in app.radio))
        next(b for b in app.button if b.label == "Ajouter une photo").click().run()
        self.assertEqual(len(app.exception), 0)
        next(w for w in app.radio if w.label == "Source des photos").set_value("Appareil photo").run()
        upload = BytesIO(image_bytes())
        upload.name = "camera.jpg"
        with patch("streamlit.camera_input", side_effect=[upload, None]):
            app.run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(next(w for w in app.text_input if w.key.endswith("_RequestReason")).value, "Conserver ce motif")

    def test_photo_controls_are_hidden_until_popup_opened(self):
        app = AppTest.from_string('from components.photos import photo_uploads\nphoto_uploads("popup_test")')
        app.run(timeout=30)
        self.assertEqual(len(app.radio), 0)
        self.assertEqual(len(app.get("file_uploader")), 0)
        self.assertEqual(len(app.get("camera_input")), 0)
        app.button(key="popup_test_open").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.radio[0].label, "Source des photos")
        self.assertIsNone(app.radio[0].value)
        self.assertEqual(len(app.get("file_uploader")), 0)
        # AppTest 1.38 relance le script complet, pas le fragment du dialogue.
        app = AppTest.from_string('from components.photos import photo_dialog\nphoto_dialog("popup_test")').run()
        app.radio[0].set_value("Document / galerie").run()
        self.assertEqual(len(app.get("file_uploader")), 1)

    def test_record_dialog_switches_to_photos_and_restores_fields(self):
        app = AppTest.from_string('''
from components.dossier_forms import record_dialog
record_dialog("prestations", "REQ-test", parent={"WorkOrderReferenceEnrobEau": "WO-test", "WorkOrderReferenceSaur": "SAUR-test"})
''').run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        reason = next(w for w in app.text_input if w.key.endswith("_WorkReason"))
        reason.set_value("Travaux à conserver").run()
        import streamlit as st
        rerun = st.rerun
        # Simuler les relances de fragment via une relance complète dans AppTest.
        with patch("streamlit.rerun", side_effect=lambda **kwargs: rerun()):
            next(b for b in app.button if b.label == "Ajouter une photo").click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertTrue(any(w.label == "Source des photos" for w in app.radio))
            # Reconstruire l'arbre : AppTest conserve sinon les anciens widgets
            # du dialogue que Streamlit a déjà retirés de la session.
            state = app.session_state.filtered_state
            app = AppTest.from_string('from components.dossier_forms import record_dialog\nrecord_dialog("prestations", "REQ-test", parent={"WorkOrderReferenceEnrobEau": "WO-test", "WorkOrderReferenceSaur": "SAUR-test"})')
            for key, value in state.items():
                app.session_state[key] = value
            app.run()
            next(b for b in app.button if b.label == "Terminer").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(next(w for w in app.text_input if w.key.endswith("_WorkReason")).value, "Travaux à conserver")

    def test_forms_edit_is_saved_and_does_not_load_photos(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "pages/forms.py"))
        app.session_state["current_user"] = {"actif": True, "profil": "agent", "email": self.email}
        with patch.object(photos, "read_photo", side_effect=AssertionError("Lecture prématurée")):
            app.run(timeout=30)
            app.button(key=f"forms_view_{self.ref}").click().run(timeout=30)
            app.button(key="forms_modify").click().run(timeout=30)
            app.text_input(key=f"{self.ref}_RequestReason").set_value("Motif modifié")
            next(b for b in app.button if b.label == "Enregistrer les modifications").click().run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(next(r for r in load_store()["demandes"] if r["RequestReference"] == self.ref)["RequestReason"], "Motif modifié")

    def test_refection_page_filters_opens_correct_record_and_keeps_request_photos_read_only(self):
        from services.refection_service import prestation_rows
        row = prestation_rows(self.store)[0]
        service_ref, request_ref = row["ServiceReference"], row["RequestReference"]
        photos.add_photos("demandes", request_ref, [self.photo], self.email)
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "pages/reporting.py"))
        app.session_state["current_user"] = {"actif": True, "profil": "agent externe", "email": self.email}
        with patch.object(photos, "read_photo", side_effect=AssertionError("Lecture prématurée")):
            app.run(timeout=30)
            app.text_input(key="refection_query").set_value(service_ref).run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.dataframe[0].value), 1)
            self.assertEqual(app.session_state["refection_selected"], service_ref)
            self.assertEqual(len([b for b in app.button if b.label == "Ajouter une photo"]), 1)
            self.assertFalse(any(b.key and b.key.startswith(f"photos_demandes_{request_ref}") for b in app.button))
            with patch("components.dossier_forms.record_dialog") as dialog:
                app.button(key="refection_edit").click().run()
            self.assertEqual(dialog.call_args.args, ("prestations", request_ref))
            original = dialog.call_args.kwargs["original"]
            self.assertEqual(original["ServiceReference"], service_ref)
            app.text_input(key="refection_query").set_value("inexistant-xyz").run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.dataframe), 0)
        # Vérifier la sauvegarde du formulaire réellement utilisé par le dialogue.
        form = AppTest.from_string('''
import streamlit as st
from components.dossier_forms import render_record_form
render_record_form("prestations", st.session_state.request_ref, original=st.session_state.original)
''')
        form.session_state["current_user"] = {"actif": True, "profil": "agent externe", "email": self.email}
        form.session_state["request_ref"] = request_ref
        form.session_state["original"] = original
        form.run(timeout=30)
        next(w for w in form.text_input if w.key.endswith("_WorkReason")).set_value("Travaux sous-traitant")
        next(b for b in form.button if b.label == "Enregistrer les modifications").click().run()
        self.assertFalse(form.exception)
        # L'exemple d'origine indique Non pour le béton sans date : la règle
        # existante impose de compléter cette date avant tout enregistrement.
        self.assertTrue(any("Saisissez manuellement" in error.value for error in form.error))
        from datetime import date
        next(w for w in form.date_input if w.key.endswith("_Concrete2CmDate")).set_value(date(2026, 9, 18))
        next(b for b in form.button if b.label == "Enregistrer les modifications").click().run()
        self.assertFalse(form.exception)
        self.assertFalse(form.error)
        saved = next(r for r in load_store()["prestations"] if r["ServiceReference"] == service_ref)
        self.assertEqual(saved["WorkReason"], "Travaux sous-traitant")

    def test_request_photos_read_only_ignores_stale_edit_and_upload_state(self):
        photos.add_photos("demandes", self.ref, [self.photo], self.email)
        photo_id = photos.list_photos("demandes", self.ref)[0]["PhotoReference"]
        for profile in ["agent externe", "administrateur"]:
            app = AppTest.from_string(f'from components.photos import render_photos\nrender_photos("demandes", "{self.ref}", read_only=True)')
            app.session_state["current_user"] = {"actif": True, "profil": profile}
            prefix = f"photos_demandes_{self.ref}"
            app.session_state[f"{prefix}_edit"] = photo_id
            app.session_state[f"{prefix}_delete"] = photo_id
            app.session_state[f"{prefix}_add_queue"] = [dict(self.photo, DraftId="pending")]
            app.run(timeout=30)
            self.assertFalse(app.exception)
            self.assertEqual(len(app.button), 0)
            self.assertEqual(len(app.text_input), 0)
            self.assertEqual(len(app.get("link_button")), 1)
