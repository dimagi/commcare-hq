import json
from django.test import SimpleTestCase
from mock import patch

from corehq.apps.app_manager.models import AdvancedForm, Form, PreloadAction
from corehq.apps.app_manager.views.forms import _get_case_references


class FormCaseReferenceTest(SimpleTestCase):

    def setUp(self):
        self.form = Form()

    def test_one_reference_old_format(self):
        post_data = {
            "references": json.dumps({
                "preload": {
                    "/data/question": "name"
                },
                "condition": {
                    "answer": None,
                    "question": None,
                    "type": "always",
                    "operator": None,
                }
            })
        }
        self.form.case_references = _get_case_references(post_data)
        self.assertEqual(self.form.case_references,
            {"load": {"/data/question": ["name"]}})
        self.assertFalse(self.form.actions.load_from_form.preload)

    def test_two_references(self):
        refs = {
            "load": {
                "/data/question": ["name", "dob"],
                "/data/other_question": ["close_reason"],
            },
        }
        post_data = {"case_references": json.dumps(refs)}
        self.form.case_references = _get_case_references(post_data)
        self.assertEqual(self.form.case_references, refs)
        self.assertFalse(self.form.actions.load_from_form.preload)

    def test_legacy_preload_action_case_references(self):
        self.form.actions.load_from_form = PreloadAction({
            "preload": {
                "/data/question": "name"
            },
            "condition": {
                "answer": None,
                "question": None,
                "type": "always",
                "operator": None,
            }
        })
        self.assertEqual(self.form.case_references,
            {"load": {"/data/question": ["name"]}})


class AdvancedFormCaseReferenceTest(SimpleTestCase):

    def setUp(self):
        self.form = AdvancedForm()

    def test_one_reference(self):
        post_data = {
            "references": json.dumps({
                "preload": {
                    "/data/question": "name"
                },
                "condition": {
                    "answer": None,
                    "question": None,
                    "type": "always",
                    "operator": None,
                }
            })
        }
        self.form.case_references = _get_case_references(post_data)
        self.assertEqual(self.form.case_references, {})
        self.assertFalse(hasattr(self.form.actions, "load_from_form"))

    def test_two_references(self):
        refs = {
            "load": {
                "/data/question": ["name", "dob"],
                "/data/other_question": ["close_reason"],
            },
        }
        post_data = {"case_references": json.dumps(refs)}
        self.form.case_references = _get_case_references(post_data)
        self.assertEqual(self.form.case_references, {})
        self.assertFalse(hasattr(self.form.actions, "load_from_form"))
