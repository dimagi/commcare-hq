from __future__ import absolute_import
from __future__ import unicode_literals
import json
from django.test import SimpleTestCase
from corehq.util.test_utils import generate_cases

from corehq.apps.app_manager.models import AdvancedForm, Form, PreloadAction, CaseReferences, CaseSaveReference
from corehq.apps.app_manager.views.forms import _get_case_references


def _assert_references_equal(testcase, wrapped_references, unwrapped_references):
    testcase.assertEqual(
        wrapped_references.to_json(),
        CaseReferences.wrap(unwrapped_references).to_json(),
    )


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
        _assert_references_equal(
            self,
            self.form.case_references,
            {"load": {"/data/question": ["name"]}}
        )
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
        _assert_references_equal(self, self.form.case_references, refs)
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
        _assert_references_equal(
            self,
            self.form.case_references,
            {"load": {"/data/question": ["name"]}}
        )


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
        _assert_references_equal(self, self.form.case_references, {"load": {"/data/question": ["name"]}})
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
        _assert_references_equal(self, self.form.case_references, refs)
        self.assertFalse(hasattr(self.form.actions, "load_from_form"))


@generate_cases([
    ({},),
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
    _assert_references_equal(self, _get_case_references(wrapped_references), case_references)


@generate_cases([
    ({'load': {'data/non-strings': [0, 'p2']}},),
    ({'load': {}, 'extra': 'stuff'},),
    ({'load': {}, 'save': {'data/extra': {'extra': 'stuff'}}},),
    ({'load': {}, 'save': {'data/non-strings': {'properties': [0, 'p2']}}},),
    ({'load': {}, 'save': {'data/create-non-bool': {'create': 'abc'}}},),
    ({'load': {}, 'save': {'data/close-non-bool': {'close': 0}}},),
])
def test_invalid_args(self, case_references):
    with self.assertRaises(ValueError):
        wrapped_references = {
            'case_references': json.dumps(case_references)
        }
        _get_case_references(wrapped_references)


class CaseReferencesTest(SimpleTestCase):

    def test_get_load_refs(self):
        load = {
            'path1': ['p1', 'p2'],
            'path2': ['p3'],
        }
        case_refs = CaseReferences(
            load=load,
        )
        load_refs = list(case_refs.get_load_references())
        self.assertEqual(2, len(load_refs))
        for load_ref in load_refs:
            self.assertEqual(load[load_ref.path], load_ref.properties)

    def test_get_save_refs(self):
        save = {
            'path1': CaseSaveReference(case_type='foo', properties=['p1', 'p2']),
            'path2': CaseSaveReference(properties=['p3'], create=True, close=True),
        }
        case_refs = CaseReferences(
            save=save,
        )
        save_refs = list(case_refs.get_save_references())
        self.assertEqual(2, len(save_refs))
        for save_ref in save_refs:
            orig_ref = save[save_ref.path]
            for attr in ('case_type', 'properties', 'create', 'close'):
                self.assertEqual(getattr(orig_ref, attr), getattr(save_ref, attr))

    def test_get_save_refs_dont_mutate_app(self):
        case_refs = CaseReferences(load={}, save={
            'p1': CaseSaveReference(properties=['p1', 'p2'])
        })
        save_ref = next(case_refs.get_save_references())
        save_ref.properties.append('p3')
        self.assertEqual(['p1', 'p2', 'p3'], save_ref.properties)
        self.assertEqual(['p1', 'p2'], case_refs.save['p1'].properties)
