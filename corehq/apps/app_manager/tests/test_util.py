import corehq.apps.app_manager.util as util
from corehq.apps.app_manager.models import (
    Module,
    AdvancedModule,
    FormSchedule,
    ScheduleVisit
)
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import TestXmlMixin
from django.test.testcases import SimpleTestCase
from mock import patch, MagicMock
import re


@patch('corehq.apps.app_manager.util.get_per_type_defaults', MagicMock(return_value={}))
class GetCasePropertiesTest(SimpleTestCase, TestXmlMixin):
    file_path = ('data',)

    def assertCaseProperties(self, app, case_type, expected_properties):
        properties = util.get_case_properties(app, [case_type])
        self.assertEqual(
            set(properties[case_type]),
            set(expected_properties),
        )

    def test_basic_apps(self):
        for class_ in (Module, AdvancedModule):
            factory = AppFactory()
            m1, m1f1 = factory.new_module(class_, 'open_case', 'house')
            factory.form_opens_case(m1f1)
            m1f2 = factory.new_form(m1)
            factory.form_requires_case(m1f2, case_type='house', update={
                'foo': '/data/question1',
                'bar': '/data/question2',
            })
            self.assertCaseProperties(factory.app, 'house', ['foo', 'bar'])

    def test_scheduler_module(self):
        factory = AppFactory()
        m1, m1f1 = factory.new_basic_module('open_case', 'house')
        factory.form_opens_case(m1f1)
        m2, m2f1 = factory.new_advanced_module('scheduler_module', 'house')
        m2f2 = factory.new_form(m2)
        factory.form_requires_case(m2f1, case_type='house', update={
            'foo': '/data/question1',
            'bar': '/data/question2',
        })
        factory.form_requires_case(m2f2, case_type='house', update={
            'bleep': '/data/question1',
            'bloop': '/data/question2',
        })

        self._add_scheduler_to_module(m2)
        self._add_scheduler_to_form(m2f1, m2, 'form1')
        self._add_scheduler_to_form(m2f2, m2, 'form2')

        self.assertCaseProperties(factory.app, 'house', [
            'foo',
            'bar',
            'bleep',
            'bloop',
            # Scheduler properties:
            'last_visit_date_form1',
            'last_visit_number_form1',
            'last_visit_date_form2',
            'last_visit_number_form2',
            'current_schedule_phase',
        ])

    def _add_scheduler_to_module(self, module):
        # (this mimics the behavior in app_manager.views.schedules.edit_schedule_phases()
        module.update_schedule_phase_anchors([(1, 'date-opened')])
        module.update_schedule_phases(['date-opened'])
        module.has_schedule = True

    def _add_scheduler_to_form(self, form, module, form_abreviation):
        # (this mimics the behavior in app_manager.views.schedules.edit_visit_schedule()
        # A Form.source is required to retreive scheduler properties
        form.source = self.get_xml('very_simple_form')
        phase, _ = module.get_or_create_schedule_phase(anchor='date-opened')
        form.schedule_form_id = form_abreviation
        form.schedule = FormSchedule(
            starts=5,
            expires=None,
            visits=[
                ScheduleVisit(due=7, expires=5, starts=-2),
            ]
        )
        phase.add_form(form)


@patch('corehq.apps.app_manager.models.is_usercase_in_use', MagicMock(return_value=False))
@patch('corehq.apps.app_manager.util.get_per_type_defaults', MagicMock(return_value={}))
class SchemaTest(SimpleTestCase):
    def setUp(self):
        self.factory = AppFactory()
        self.factory_2 = AppFactory()

    def test_get_casedb_schema_form_without_cases(self):
        survey = self.add_form()
        schema = util.get_casedb_schema(survey)
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
        schema = util.get_casedb_schema(village)
        self.assertEqual(len(schema["subsets"]), 1, schema["subsets"])
        self.assert_has_kv_pairs(schema["subsets"][0], {
            'id': 'case',
            'name': 'village',
            'key': '@case_type',
            'structure': {'case_name': {}},
            'related': None,
        })

    def test_get_casedb_schema_with_related_case_types(self):
        family = self.add_form("family")
        village = self.add_form("village")
        self.factory.form_opens_case(village, case_type='family', is_subcase=True)
        schema = util.get_casedb_schema(family)
        subsets = {s["id"]: s for s in schema["subsets"]}
        self.assertEqual(subsets["parent"]["related"], None)
        self.assertDictEqual(subsets["case"]["related"], {"parent": "parent"})

    def test_get_casedb_schema_with_multiple_parent_case_types(self):
        referral = self.add_form("referral")
        child = self.add_form("child")
        self.factory.form_opens_case(child, case_type='referral', is_subcase=True)
        pregnancy = self.add_form("pregnancy")
        self.factory.form_opens_case(pregnancy, case_type='referral', is_subcase=True)
        schema = util.get_casedb_schema(referral)
        subsets = {s["id"]: s for s in schema["subsets"]}
        self.assertTrue(re.match(r'^parent \((pregnancy|child) or (pregnancy|child)\)$',
                        subsets["parent"]["name"]))
        self.assertEqual(subsets["parent"]["structure"], {"case_name": {}})

    def test_get_casedb_schema_with_deep_hierarchy(self):
        child = self.add_form("child")
        parent = self.add_form("parent")
        self.factory.form_opens_case(parent, case_type='child', is_subcase=True)
        grandparent = self.add_form("grandparent")
        self.factory.form_opens_case(grandparent, case_type='parent', is_subcase=True)
        greatgrandparent = self.add_form("greatgrandparent")
        self.factory.form_opens_case(greatgrandparent, case_type='grandparent', is_subcase=True)
        schema = util.get_casedb_schema(child)
        self.assertEqual([s["name"] for s in schema["subsets"]],
                         ["child", "parent (parent)", "grandparent (grandparent)"])
        schema = util.get_casedb_schema(parent)
        self.assertEqual([s["name"] for s in schema["subsets"]],
                         ["parent", "parent (grandparent)", "grandparent (greatgrandparent)"])
        schema = util.get_casedb_schema(grandparent)
        self.assertEqual([s["name"] for s in schema["subsets"]],
                         ["grandparent", "parent (greatgrandparent)"])

    def test_get_casedb_schema_with_parent_case_property_update(self):
        family = self.add_form("family", {"parent/has_well": "/data/village_has_well"})
        village = self.add_form("village")
        self.factory.form_opens_case(village, case_type='family', is_subcase=True)
        schema = util.get_casedb_schema(family)
        subsets = {s["id"]: s for s in schema["subsets"]}
        self.assertDictEqual(subsets["case"]["related"], {"parent": "parent"})
        self.assertEqual(subsets["case"]["structure"]["case_name"], {})
        #self.assertEqual(subsets["parent"]["structure"]["has_well"], {}) TODO
        self.assertNotIn("parent/has_well", subsets["case"]["structure"])

    def test_get_session_schema_for_module_with_no_case_type(self):
        form = self.add_form()
        schema = util.get_session_schema(form)
        self.assert_has_kv_pairs(schema, {
            "id": "commcaresession",
            "uri": "jr://instance/session",
            "name": "Session",
            "path": "/session/data",
        })
        assert "case_id" not in schema["structure"], schema["structure"]

    def test_get_session_schema_for_simple_module_with_case(self):
        module, form = self.factory.new_basic_module('village', 'village')
        self.factory.form_requires_case(form)
        schema = util.get_session_schema(form)
        self.assertDictEqual(schema["structure"]["case_id"], {
            "reference": {
                "source": "casedb",
                "subset": "case",
                "key": "@case_id",
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

        casedb_schema = util.get_casedb_schema(m1f0)
        session_schema = util.get_session_schema(m1f0)

        expected_session_schema_structure = {
            "case_id_guppy": {
                "reference": {
                    "subset": "case",
                    "source": "casedb",
                    "key": "@case_id"
                }
            }
        }

        expected_casedb_schema_subsets = [
            {
                "structure": {
                    "case_name": {}
                },
                "related": {
                    "parent": "parent"
                },
                "id": "case",
                "key": "@case_type",
                "name": "guppy"
            },
            {
                "structure": {
                    "name": {},
                    "case_name": {}
                },
                "related": None,
                "id": "parent",
                "key": "@case_type",
                "name": "parent (gold-fish)"
            }
        ]

        self.assertEqual(casedb_schema['subsets'], expected_casedb_schema_subsets)
        self.assertEqual(session_schema['structure'], expected_session_schema_structure)

    def test_get_case_sharing_hierarchy(self):
        with patch('corehq.apps.app_manager.util.get_case_sharing_apps_in_domain') as mock_sharing:
            mock_sharing.return_value = [self.factory.app, self.factory_2.app]
            self.factory.app.case_sharing = True
            self.factory_2.app.case_sharing = True

            self.add_form("referral")
            child = self.add_form("child")
            self.factory.form_opens_case(child, case_type='referral', is_subcase=True)
            pregnancy = self.add_form("pregnancy")
            self.factory.form_opens_case(pregnancy, case_type='referral', is_subcase=True)
            referral_2 = self.add_form_app_2('referral')
            schema = util.get_casedb_schema(referral_2)
            subsets = {s["id"]: s for s in schema["subsets"]}
            self.assertTrue(re.match(r'^parent \((pregnancy|child) or (pregnancy|child)\)$',
                            subsets["parent"]["name"]))
            self.assertEqual(subsets["parent"]["structure"], {"case_name": {}})

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
