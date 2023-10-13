import json

from unittest.mock import patch
from testil import Regex

from corehq.apps.api.resources import v0_4
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.xform_builder import XFormBuilder
from .utils import APIResourceTest


class TestAppResource(APIResourceTest):

    resource = v0_4.ApplicationResource

    @classmethod
    def setUpClass(cls):
        super(TestAppResource, cls).setUpClass()
        cls.apps = [cls.make_app(), cls.make_app()]

        with patch('corehq.apps.app_manager.models.validate_xform', return_value=None):
            cls.apps[0].make_build().save()

    @classmethod
    def make_app(cls):
        factory = AppFactory(domain=cls.domain.name, name="API App", build_version='2.11.0')
        module1, form1 = factory.new_basic_module('open_case', 'house')
        form1.source = XFormBuilder().new_question("name", "name").form.tostring()
        factory.form_opens_case(form1)

        module2, form2 = factory.new_basic_module('update_case', 'person')
        form2.source = XFormBuilder().new_question("name", "name").form.tostring()
        factory.form_requires_case(form2, case_type='house')
        factory.form_opens_case(form2, case_type="person", is_subcase=True)

        app = factory.app
        app.save()
        return app

    def test_get_list(self):
        response = self._assert_auth_get_resource(self.list_endpoint, allow_session_auth=True)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertEqual(content["meta"], {
            'limit': None, 'next': None, 'offset': 0, 'previous': None,
            'total_count': 2
        })
        self.assertEqual(content["objects"], [
            self.get_expected_structure(with_version=True),
            self.get_expected_structure(with_version=False),
        ])

    def test_get_list_cache_bug(self):
        self.test_get_list()
        # subsequent requests use cached data which does not have the `_parent` refs set
        self.test_get_list()

    def test_get_list_null_sorting(self):
        another_app = self.make_app()
        another_app.date_created = None
        another_app.save()
        self.addCleanup(another_app.delete)
        response = self._assert_auth_get_resource(self.list_endpoint, allow_session_auth=True)
        content = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(content["meta"], {
            'limit': None, 'next': None, 'offset': 0, 'previous': None,
            'total_count': 3
        })

    def test_get_single(self):
        response = self._assert_auth_get_resource(self.single_endpoint(self.apps[0]._id), allow_session_auth=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), self.get_expected_structure(with_version=True))

    def get_expected_structure(self, with_version=False):
        xmlns = Regex(r"http://openrosa.org/formdesigner/[a-fA-F0-9\-]{36}")
        unique_id = Regex(r"[a-f0-9]{32}")
        questions = [
            {"comment": None, "constraint": None, "group": None, "hashtagValue": "#form/name", "is_group": False,
             "label": "name", "label_ref": "name-label", "relevant": None, "repeat": None, "required": False,
             "setvalue": None, "tag": "input", "translations": {"en": "name"}, "type": "Text",
             "value": "/data/name"}
        ]
        if with_version:
            versions = [{
                "id": unique_id, "build_comment": None,
                "built_on": Regex(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.\d{6}Z"),
                "is_released": False, "version": 1
            }]
        else:
            versions = []
        return {
            "name": "API App", "resource_uri": "", "version": 1,
            "build_comment": None, "built_from_app_id": None, "built_on": None, "id": unique_id,
            "versions": versions,
            "is_released": False, "modules": [
                {
                    "name": {"en": "open_case module"},
                    "unique_id": "open_case_module",
                    "case_type": "house",
                    "case_properties": ["name"],
                    "forms": [{
                        "unique_id": "open_case_form_0", "name": {"en": "open_case form 0"},
                        "questions": questions, "xmlns": xmlns
                    }],
                },
                {
                    "name": {'en': 'update_case module'},
                    "unique_id": "update_case_module",
                    "case_type": "person",
                    "case_properties": ["name"], "forms": [{
                        "unique_id": "update_case_form_0", "name": {"en": "update_case form 0"},
                        "questions": questions, "xmlns": xmlns
                    }],
                }
            ],
        }
