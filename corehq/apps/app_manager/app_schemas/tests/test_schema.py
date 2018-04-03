from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime
import re
from django.test import SimpleTestCase
from mock import patch, MagicMock
from corehq.apps.app_manager import util as util
from corehq.apps.app_manager.app_schemas.casedb_schema import get_casedb_schema
from corehq.apps.app_manager.app_schemas.session_schema import get_session_schema
from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.util.test_utils import flag_enabled


@patch('corehq.apps.app_manager.app_schemas.casedb_schema.get_case_property_description_dict',
       MagicMock(return_value={}))
@patch('corehq.apps.app_manager.models.is_usercase_in_use', MagicMock(return_value=False))
@patch('corehq.apps.app_manager.app_schemas.casedb_schema.is_usercase_in_use', MagicMock(return_value=False))
@patch('corehq.apps.app_manager.app_schemas.session_schema.is_usercase_in_use', MagicMock(return_value=False))
@patch('corehq.apps.app_manager.app_schemas.case_properties.is_usercase_in_use', MagicMock(return_value=False))
@patch('corehq.apps.app_manager.app_schemas.casedb_schema.get_per_type_defaults', MagicMock(return_value={}))
@patch('corehq.apps.app_manager.app_schemas.case_properties.get_per_type_defaults', MagicMock(return_value={}))
class SchemaTest(SimpleTestCase):
    def setUp(self):
        self.factory = AppFactory()
        self.factory_2 = AppFactory()

    def test_get_casedb_schema_form_without_cases(self):
        survey = self.add_form()
        schema = get_casedb_schema(survey)
        self.assert_has_kv_pairs(schema, {
            "id": "casedb",
            "uri": "jr://instance/casedb",
            "name": "case",
            "path": "/casedb/case",
            "structure": {},
            "subsets": [],
        })

    def test_get_casedb_schema_with_form(self):
        village = self.add_form("village")
        self.factory.form_requires_case(
            village,
            case_type=self.factory.app.get_module(0).case_type,
            update={'foo': '/data/question1'}
        )
        schema = get_casedb_schema(village)
        self.assertEqual(len(schema["subsets"]), 1, schema["subsets"])
        self.assert_has_kv_pairs(schema["subsets"][0], {
            'id': 'case',
            'name': 'village',
            'structure': {
                'case_name': {"description": ""},
                'foo': {"description": ""},
            },
            'related': None,
        })

    def test_get_casedb_schema_with_related_case_types(self):
        family = self.add_form("family")
        village = self.add_form("village")
        self.factory.form_opens_case(village, case_type='family', is_subcase=True)
        self.factory.form_requires_case(family, case_type='family', update={
            'foo': '/data/question1',
        })
        schema = get_casedb_schema(family)
        subsets = {s["id"]: s for s in schema["subsets"]}
        self.assertEqual(subsets["parent"]["related"], None)
        self.assertDictEqual(subsets["case"]["related"], {"parent": {
            "hashtag": "#case/parent",
            "subset": "parent",
            "key": "@case_id",
        }})

    def test_get_casedb_schema_with_multiple_parent_case_types(self):
        referral = self.add_form("referral")
        self.factory.form_requires_case(referral, case_type='referral', update={
            'foo': '/data/question1',
        })
        child = self.add_form("child")
        self.factory.form_opens_case(child, case_type='referral', is_subcase=True)
        pregnancy = self.add_form("pregnancy")
        self.factory.form_opens_case(pregnancy, case_type='referral', is_subcase=True)
        schema = get_casedb_schema(referral)
        subsets = {s["id"]: s for s in schema["subsets"]}
        self.assertTrue(re.match(r'^parent \((pregnancy|child) or (pregnancy|child)\)$',
                        subsets["parent"]["name"]))
        self.assertEqual(subsets["parent"]["structure"], {"case_name": {"description": ""}})

    def test_get_casedb_schema_with_deep_hierarchy(self):
        child = self.add_form("child")
        case_type = self.factory.app.get_module(0).case_type
        case_update = {'foo': '/data/question1'}
        self.factory.form_requires_case(child, case_type=case_type, update=case_update)
        parent = self.add_form("parent")
        self.factory.form_requires_case(parent, case_type=case_type, update=case_update)
        self.factory.form_opens_case(parent, case_type='child', is_subcase=True)
        grandparent = self.add_form("grandparent")
        self.factory.form_opens_case(grandparent, case_type='parent', is_subcase=True)
        self.factory.form_requires_case(grandparent, case_type=case_type, update=case_update)
        greatgrandparent = self.add_form("greatgrandparent")
        self.factory.form_opens_case(greatgrandparent, case_type='grandparent', is_subcase=True)
        schema = get_casedb_schema(child)
        self.assertEqual([s["name"] for s in schema["subsets"]],
                         ["child", "parent (parent)", "grandparent (grandparent)"])
        schema = get_casedb_schema(parent)
        self.assertEqual([s["name"] for s in schema["subsets"]],
                         ["parent", "parent (grandparent)", "grandparent (greatgrandparent)"])
        schema = get_casedb_schema(grandparent)
        self.assertEqual([s["name"] for s in schema["subsets"]],
                         ["grandparent", "parent (greatgrandparent)"])

    def test_get_casedb_schema_with_parent_case_property_update(self):
        family = self.add_form("family", {"parent/has_well": "/data/village_has_well"})
        village = self.add_form("village")
        self.factory.form_opens_case(village, case_type='family', is_subcase=True)
        schema = get_casedb_schema(family)
        subsets = {s["id"]: s for s in schema["subsets"]}
        self.assertDictEqual(subsets["case"]["related"], {"parent": {
            "hashtag": "#case/parent",
            "subset": "parent",
            "key": "@case_id",
        }})
        self.assertEqual(subsets["case"]["structure"]["case_name"], {"description": ""})
        #self.assertEqual(subsets["parent"]["structure"]["has_well"], {}) TODO
        self.assertNotIn("parent/has_well", subsets["case"]["structure"])

    def test_get_session_schema_for_module_with_no_case_type(self):
        form = self.add_form()
        schema = get_session_schema(form)
        self.assert_has_kv_pairs(schema, {
            "id": "commcaresession",
            "uri": "jr://instance/session",
            "name": "Session",
            "path": "/session",
        })
        assert "data" not in schema["structure"], schema["structure"]

    def test_get_session_schema_for_simple_module_with_case(self):
        module, form = self.factory.new_basic_module('village', 'village')
        self.factory.form_requires_case(form)
        schema = get_session_schema(form)
        self.assertDictEqual(schema["structure"], {
            "data": {
                "merge": True,
                "structure": {
                    "case_id": {
                        "reference": {
                            "hashtag": "#case",
                            "source": "casedb",
                            "subset": "case",
                            "key": "@case_id",
                        },
                    },
                },
            },
        })

    def test_get_session_schema_for_child_module(self):
        # m0 - opens 'gold-fish' case.
        # m1 - has m0 as root-module, has parent-select, updates 'guppy' case
        self.module_0, _ = self.factory.new_basic_module('parent', 'gold-fish')
        self.module_1, _ = self.factory.new_basic_module('child', 'guppy', parent_module=self.module_0)
        # m0f0 registers gold-fish case and a child case ('guppy')
        m0f0 = self.module_0.get_form(0)
        self.factory.form_requires_case(m0f0, update={'name': 'goldilocks'})
        self.factory.form_opens_case(m0f0, 'guppy', is_subcase=True)

        # m1f0 has parent-select, updates `guppy` case
        m1f0 = self.module_1.get_form(0)
        self.factory.form_requires_case(m1f0, parent_case_type='gold-fish')

        casedb_schema = get_casedb_schema(m1f0)
        session_schema = get_session_schema(m1f0)

        expected_session_schema_structure = {
            "data": {
                "merge": True,
                "structure": {
                    "case_id_guppy": {
                        "reference": {
                            "hashtag": "#case",
                            "subset": "case",
                            "source": "casedb",
                            "key": "@case_id"
                        }
                    }
                }
            }
        }

        expected_casedb_schema_subsets = [
            {
                "structure": {
                    "case_name": {
                        "description": "",
                    }
                },
                "related": {
                    "parent": {
                        "hashtag": "#case/parent",
                        "subset": "parent",
                        "key": "@case_id",
                    }
                },
                "id": "case",
                "name": "guppy"
            },
            {
                "structure": {
                    "name": {
                        "description": "",
                    },
                    "case_name": {
                        "description": "",
                    }
                },
                "related": None,
                "id": "parent",
                "name": "parent (gold-fish)"
            }
        ]

        self.assertEqual(casedb_schema['subsets'], expected_casedb_schema_subsets)
        self.assertEqual(session_schema['structure'], expected_session_schema_structure)

    def test_get_case_sharing_hierarchy(self):
        with patch('corehq.apps.app_manager.app_schemas.case_properties.get_case_sharing_apps_in_domain')\
                as mock_sharing:
            mock_sharing.return_value = [self.factory.app, self.factory_2.app]
            self.factory.app.case_sharing = True
            self.factory_2.app.case_sharing = True

            self.add_form("referral")
            child = self.add_form("child")
            self.factory.form_opens_case(child, case_type='referral', is_subcase=True)
            pregnancy = self.add_form("pregnancy")
            self.factory.form_opens_case(pregnancy, case_type='referral', is_subcase=True)
            schema = get_casedb_schema(pregnancy)
            subsets = {s["id"]: s for s in schema["subsets"]}
            self.assertEqual(subsets, {})

            referral_2 = self.add_form_app_2('referral')
            self.factory.form_requires_case(referral_2, case_type='referral', update={
                'foo': '/data/question1',
            })
            schema = get_casedb_schema(referral_2)
            subsets = {s["id"]: s for s in schema["subsets"]}
            self.assertTrue(re.match(r'^parent \((pregnancy|child) or (pregnancy|child)\)$',
                            subsets["parent"]["name"]))
            self.assertEqual(subsets["parent"]["structure"], {"case_name": {"description": ""}})

    def test_get_session_schema_with_user_case(self):
        module, form = self.factory.new_basic_module('village', 'village')
        with patch('corehq.apps.app_manager.app_schemas.casedb_schema.is_usercase_in_use') as mock1, \
                patch('corehq.apps.app_manager.app_schemas.session_schema.is_usercase_in_use') as mock2:
            mock1.return_value = True
            mock2.return_value = True
            schema = get_session_schema(form)
            self.assertDictEqual(schema["structure"]["context"], {
                "merge": True,
                "structure": {
                    "userid": {
                        "reference": {
                            "hashtag": "#user",
                            "source": "casedb",
                            "subset": util.USERCASE_TYPE,
                            "subset_key": "@case_type",
                            "subset_filter": True,
                            "key": "hq_user_id",
                        },
                    },
                },
            })

    def test_get_casedb_schema_with_user_case(self):
        module, form = self.factory.new_basic_module('village', 'village')
        self.factory.form_uses_usercase(form, update={
            'name': '/data/username',
            'role': '/data/userrole',
        })
        with patch('corehq.apps.app_manager.app_schemas.casedb_schema.is_usercase_in_use') as mock1, \
                patch('corehq.apps.app_manager.app_schemas.case_properties.is_usercase_in_use') as mock2:
            mock1.return_value = True
            mock2.return_value = True
            schema = get_casedb_schema(form)
            subsets = {s["id"]: s for s in schema["subsets"]}
            self.assertDictEqual(subsets[USERCASE_TYPE], {
                "id": USERCASE_TYPE,
                "key": "@case_type",
                "name": "user",
                "structure": {
                    "name": {},
                    "role": {},
                    "first_name": {},
                    "last_name": {},
                    "username": {},
                    "phone_number": {},
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

    def add_form(self, case_type=None, case_updates=None):
        module_id = len(self.factory.app.modules)
        module, form = self.factory.new_basic_module(module_id, case_type)
        if case_type:
            self.factory.form_opens_case(form, case_type)
        if case_updates:
            assert case_type, 'case_type is required with case_updates'
            self.factory.form_requires_case(
                form, case_type=case_type, update=case_updates)
        return form

    def add_form_app_2(self, case_type=None, case_updates=None):
        module_id = len(self.factory_2.app.modules)
        module, form = self.factory_2.new_basic_module(module_id, case_type)
        if case_type:
            self.factory_2.form_opens_case(form, case_type)
        if case_updates:
            assert case_type, 'case_type is required with case_updates'
            self.factory_2.form_requires_case(
                form, case_type=case_type, update=case_updates)
        return form
