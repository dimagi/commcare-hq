import json
from django.test import SimpleTestCase
from corehq.util.test_utils import generate_cases

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
        self.assertEqual(self.form.case_references, {"load": {"/data/question": ["name"]}})
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
        self.assertEqual(self.form.case_references, refs)
        self.assertFalse(hasattr(self.form.actions, "load_from_form"))


@generate_cases([
    ({'load': {}},),
    ({'load': {'data/empty': []}},),
    ({'load': {'data/properties': ['p1', 'p2']}},),
    ({'load': {'data/multiple1': ['p1', 'p2'], 'data/multiple2': ['p1', 'p2']}},),
    ({'load': {}, 'save': {}},),
    ({'load': {}, 'save': {'data/empty': {}}},),
    ({'load': {}, 'save': {'data/case_type': {'case_type': 'ct'}}},),
    ({'load': {}, 'save': {'data/props': {'properties': ['p1', 'p2']}}},),
    ({'load': {}, 'save': {'data/create': {'create': True}}},),
    ({'load': {}, 'save': {'data/close': {'close': True}}},),
    ({
         'load': {
             'data/load1': ['p1', 'p2'],
             'data/load2': ['p1', 'p2']
         },
         'save': {
             'data/save1': {
                 'case_type': 'foo_type',
                 'properties': ['p1', 'p2'],
                 'create': True,
                 'close': True,
              },
             'data/save2': {
                 'case_type': 'foo_type',
                 'properties': ['p1', 'p2'],
                 'create': True,
                 'close': True,
              }
         }
     },),
])
def test_valid_args(self, case_references):
    wrapped_references = {
        'case_references': json.dumps(case_references)
    }
    self.assertEqual(case_references, _get_case_references(wrapped_references))


@generate_cases([
    ({},),
    ({'load': {'data/non-strings': [0, 'p2']}},),
    ({'load': {}, 'extra': 'stuff'},),
    ({'load': {}, 'save': {'data/extra': {'extra': 'stuff'}}},),
    ({'load': {}, 'save': {'data/non-strings': {'properties': [0, 'p2']}}},),
    ({'load': {}, 'save': {'data/create-non-bool': {'create': 'abc'}}},),
    ({'load': {}, 'save': {'data/close-non-bool': {'close': 0}}},),
])
def test_invalid_args(self, case_references):
    with self.assertRaises(Exception):
        wrapped_references = {
            'case_references': json.dumps(case_references)
        }
        _get_case_references(wrapped_references)
