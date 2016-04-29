from django.test import SimpleTestCase
from mock import patch

from corehq.apps.app_manager.models import AdvancedForm, Form, PreloadAction
from corehq.apps.app_manager.views.forms import _update_case_refs_from_form_builder


class FormCaseReferenceTest(SimpleTestCase):
    def setUp(self):
        self.form = Form()

    def testOneReference(self):
        ref_json = {
            "preload": {
                "/data/question": "name"
            },
            "condition": {
                "answer": None,
                "question": None,
                "type": "always",
                "operator": None,
            }
        }
        _update_case_refs_from_form_builder(self.form, ref_json)
        self.assertEqual(self.form.actions.load_from_form.to_json(), ref_json)

    def testTwoReferences(self):
        ref_json = {
            "preload": {
                "/data/question": "name",
                "/data/other_question": "close_reason"
            },
            "condition": {
                "answer": None,
                "question": None,
                "type": "always",
                "operator": None,
            }
        }
        _update_case_refs_from_form_builder(self.form, ref_json)
        self.assertEqual(self.form.actions.load_from_form.to_json(), ref_json)


class AdvancedFormCaseReferenceTest(SimpleTestCase):
    def setUp(self):
        self.form = AdvancedForm()

    def testOneReference(self):
        ref_json = {
            "preload": {
                "/data/question": "name"
            },
            "condition": {
                "answer": None,
                "question": None,
                "type": "always",
                "operator": None,
            }
        }
        with patch.object(PreloadAction, 'wrap') as mock:
            _update_case_refs_from_form_builder(self.form, ref_json)
            self.assertFalse(mock.called)

    def testTwoReferences(self):
        ref_json = {
            "preload": {
                "/data/question": "name",
                "/data/other_question": "close_reason"
            },
            "condition": {
                "answer": None,
                "question": None,
                "type": "always",
                "operator": None,
            }
        }
        with patch.object(PreloadAction, 'wrap') as mock:
            _update_case_refs_from_form_builder(self.form, ref_json)
            self.assertFalse(mock.called)
