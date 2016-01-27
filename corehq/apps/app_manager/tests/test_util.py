import corehq.apps.app_manager.util as util
from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import (
    Application, Module, OpenCaseAction, OpenSubCaseAction)
from django.test.testcases import SimpleTestCase
from mock import patch


class SchemaTest(SimpleTestCase):

    def setUp(self):
        self.models_is_usercase_in_use_patch = patch('corehq.apps.app_manager.models.is_usercase_in_use')
        self.models_is_usercase_in_use_mock = self.models_is_usercase_in_use_patch.start()
        self.models_is_usercase_in_use_mock.return_value = False
        self.util_is_usercase_in_use_patch = patch('corehq.apps.app_manager.util.is_usercase_in_use')
        self.util_is_usercase_in_use_mock = self.util_is_usercase_in_use_patch.start()
        self.util_is_usercase_in_use_mock.return_value = False

    def tearDown(self):
        self.models_is_usercase_in_use_patch.stop()
        self.util_is_usercase_in_use_patch.stop()

    def test_get_casedb_schema_empty_app(self):
        app = self.make_app()
        schema = util.get_casedb_schema(app)
        self.assert_has_kv_pairs(schema, {
            "id": "casedb",
            "uri": "jr://instance/casedb",
            "name": "case",
            "path": "/casedb/case",
            "structure": {},
            "subsets": [],
        })

    def test_get_casedb_schema_with_form(self):
        app = self.make_app()
        self.add_form(app, "village")
        schema = util.get_casedb_schema(app)
        self.assertEqual(len(schema["subsets"]), 1, schema["subsets"])
        self.assert_has_kv_pairs(schema["subsets"][0], {
            'id': 'village',
            'key': '@case_type',
            'structure': {'case_name': {}},
            'related': None,
        })

    def test_get_casedb_schema_with_related_case_types(self):
        app = self.make_app()
        self.add_form(app, "family")
        village = self.add_form(app, "village")
        village.actions.subcases.append(OpenSubCaseAction(
            case_type='family',
            reference_id='parent'
        ))
        schema = util.get_casedb_schema(app)
        subsets = {s["id"]: s for s in schema["subsets"]}
        self.assertEqual(subsets["village"]["related"], None)
        self.assertDictEqual(subsets["family"]["related"], {"parent": "village"})

    def test_get_session_schema_for_user_registration_form(self):
        app = self.make_app()
        schema = util.get_session_schema(app.user_registration)
        self.assert_has_kv_pairs(schema, {
            "id": "commcaresession",
            "uri": "jr://instance/session",
            "name": "Session",
            "path": "/session/data",
        })
        assert "case_id" not in schema["structure"], schema["structure"]

    def test_get_session_schema_for_module_with_no_case_type(self):
        app = self.make_app()
        form = self.add_form(app)
        schema = util.get_session_schema(form)
        self.assert_has_kv_pairs(schema, {
            "id": "commcaresession",
            "uri": "jr://instance/session",
            "name": "Session",
            "path": "/session/data",
        })
        assert "case_id" not in schema["structure"], schema["structure"]

    def test_get_session_schema_for_simple_module_with_case(self):
        app = self.make_app()
        form = self.add_form(app, "village")
        schema = util.get_session_schema(form)
        self.assertDictEqual(schema["structure"]["case_id"], {
            "reference": {
                "source": "casedb",
                "subset": "village",
                "key": "@case_id",
            },
        })

    # -- helpers --

    def assert_has_kv_pairs(self, test_dict, expected_dict):
        """Assert that test_dict contains all key/value pairs in expected_dict

        Key/value pairs in `test_dict` but not present in
        `expected_dict` will be ignored.
        """
        for key, value in expected_dict.items():
            self.assertEqual(test_dict[key], value)

    def add_form(self, app, case_type=None, module_id=None):
        if module_id is None:
            module_id = len(app.modules)
            m = app.add_module(Module.new_module('Module{}'.format(module_id), lang='en'))
            if case_type:
                m.case_type = case_type
        form = app.new_form(module_id, 'form {}'.format(case_type), lang='en')
        if case_type:
            form.actions.open_case = OpenCaseAction(name_path="/data/question1", external_id=None)
            form.actions.open_case.condition.type = 'always'
        return form

    def make_app(self):
        app = Application.new_app('domain', 'New App', APP_V2)
        app.version = 1
        return app
