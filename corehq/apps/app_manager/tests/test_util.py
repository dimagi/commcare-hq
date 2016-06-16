import corehq.apps.app_manager.util as util
from corehq.apps.app_manager.models import (
    Module,
    AdvancedModule,
    FormSchedule,
    ScheduleVisit
)
from corehq.apps.app_manager.tests import TestXmlMixin, AppFactory
from django.test.testcases import SimpleTestCase
from mock import patch, MagicMock


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

    def test_get_casedb_schema_empty_app(self):
        schema = util.get_casedb_schema(self.factory.app)
        self.assert_has_kv_pairs(schema, {
            "id": "casedb",
            "uri": "jr://instance/casedb",
            "name": "case",
            "path": "/casedb/case",
            "structure": {},
            "subsets": [],
        })

    def test_get_casedb_schema_with_form(self):
        self.add_form("village")
        schema = util.get_casedb_schema(self.factory.app)
        self.assertEqual(len(schema["subsets"]), 1, schema["subsets"])
        self.assert_has_kv_pairs(schema["subsets"][0], {
            'id': 'village',
            'key': '@case_type',
            'structure': {'case_name': {}},
            'related': None,
        })

    def test_get_casedb_schema_with_related_case_types(self):
        self.add_form("family")
        village = self.add_form("village")
        self.factory.form_opens_case(village, case_type='family', is_subcase=True)
        schema = util.get_casedb_schema(self.factory.app)
        subsets = {s["id"]: s for s in schema["subsets"]}
        self.assertEqual(subsets["village"]["related"], None)
        self.assertDictEqual(subsets["family"]["related"], {"parent": "village"})

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
                "subset": "village",
                "key": "@case_id",
            },
        })

    def test_get_session_schema_form_parent_child_case(self):
        self.factory.new_basic_module('child visit', 'child')
        m2, m2f0 = self.factory.new_basic_module('child visit', 'visit')
        self.factory.form_requires_case(m2f0, parent_case_type='child')

        schema = util.get_session_schema(m2f0)
        self.assertDictEqual(schema["structure"], {
            'parent_id': {
                "reference": {
                    "source": "casedb",
                    "subset": "child",
                    "key": "@case_id",
                }
            },
            'case_id': {
                "reference": {
                    "source": "casedb",
                    "subset": "visit",
                    "key": "@case_id",
                }
            }
        })

    def test_get_session_schema_advanced_form(self):
        m2, m2f0 = self.factory.new_advanced_module('visit history', 'visit')
        self.factory.form_requires_case(m2f0, 'visit')

        schema = util.get_session_schema(m2f0)
        self.assertDictEqual(schema["structure"]["case_id_load_visit_0"], {
            "reference": {
                "source": "casedb",
                "subset": "visit",
                "key": "@case_id",
            },
        })

    def test_get_session_schema_advanced_form_multiple_cases(self):
        self.factory.new_advanced_module('visit history', 'child')
        m2, m2f0 = self.factory.new_advanced_module('visit history', 'visit')
        self.factory.form_requires_case(m2f0, 'child')
        self.factory.form_requires_case(m2f0, 'visit', parent_case_type='child')

        schema = util.get_session_schema(m2f0)
        self.assertDictEqual(schema["structure"], {
            'case_id_load_child_0': {
                "reference": {
                    "source": "casedb",
                    "subset": "child",
                    "key": "@case_id",
                }
            },
            'case_id_load_visit_0': {
                "reference": {
                    "source": "casedb",
                    "subset": "visit",
                    "key": "@case_id",
                }
            }
        })

    def test_get_session_schema_form_child_module(self):
        self.module_0, m0f0 = self.factory.new_basic_module('parent', 'gold-fish')
        self.module_1, m1f0 = self.factory.new_basic_module('child', 'guppy', parent_module=self.module_0)
        self.factory.form_requires_case(m0f0)
        self.factory.form_opens_case(m0f0, 'guppy', is_subcase=True)

        self.factory.form_requires_case(m1f0, 'gold-fish')
        self.factory.form_requires_case(m1f0, 'guppy', parent_case_type='gold-fish')

        schema = util.get_session_schema(m1f0)
        self.assertDictEqual(schema["structure"], {
            'case_id': {
                "reference": {
                    "source": "casedb",
                    "subset": "gold-fish",
                    "key": "@case_id",
                }
            },
            'case_id_guppy': {
                "reference": {
                    "source": "casedb",
                    "subset": "guppy",
                    "key": "@case_id",
                }
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

    def add_form(self, case_type=None):
        module_id = len(self.factory.app.modules)
        module, form = self.factory.new_basic_module(module_id, case_type)
        if case_type:
            self.factory.form_opens_case(form, case_type)
        return form
