from __future__ import absolute_import, unicode_literals

from django.test.testcases import TestCase

from corehq.apps.app_manager.app_schemas.form_metadata import (
    get_app_summary_formdata,
)
from corehq.apps.app_manager.models import (
    AdvancedModule,
    Application,
    LoadUpdateAction,
)
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.xform_builder import XFormBuilder


class TestGetFormData(TestCase):
    def _build_app_with_groups(self, factory):
        module1, form1 = factory.new_basic_module('open_case', 'household')
        form1_builder = XFormBuilder(form1.name)

        # question 0
        form1_builder.new_question('name', 'Name')

        # question 1 (a group)
        form1_builder.new_group('demographics', 'Demographics')
        # question 2 (a question in a group)
        form1_builder.new_question('age', 'Age', group='demographics')
        # question 3 (a question that has a load property)
        form1_builder.new_question('polar_bears_seen', 'Number of polar bears seen')

        form1.source = form1_builder.tostring(pretty_print=True).decode('utf-8')
        factory.form_requires_case(form1, case_type='household', update={
            'name': '/data/name',
            'age': '/data/demographics/age',
        }, preload={
            '/data/polar_bears_seen': 'polar_bears_seen',
        })
        factory.app.save()

    def test_form_data_with_case_properties(self):
        factory = AppFactory()
        self._build_app_with_groups(factory)
        app = factory.app

        modules, errors = get_app_summary_formdata(app.domain, app)

        q1_saves = modules[0]['forms'][0]['questions'][0]['save_properties'][0]
        self.assertEqual(q1_saves.case_type, 'household')
        self.assertEqual(q1_saves.property, 'name')

        group_saves = modules[0]['forms'][0]['questions'][1]['children'][0]['save_properties'][0]
        self.assertEqual(group_saves.case_type, 'household')
        self.assertEqual(group_saves.property, 'age')

        q3_loads = modules[0]['forms'][0]['questions'][2]['load_properties'][0]
        self.assertEqual(q3_loads.case_type, 'household')
        self.assertEqual(q3_loads.property, 'polar_bears_seen')

    def test_advanced_form_get_action_type(self):
        app = Application.new_app('domain', "Untitled Application")

        parent_module = app.add_module(AdvancedModule.new_module('parent', None))
        parent_module.case_type = 'parent'
        parent_module.unique_id = 'id_parent_module'

        form = app.new_form(0, "Untitled Form", None)
        form.xmlns = 'http://id_m1-f0'
        form.actions.load_update_cases.append(LoadUpdateAction(case_type="clinic", case_tag='load_0'))

        modules, errors = get_app_summary_formdata('domain', app)
        self.assertEqual(modules[0]['forms'][0]['action_type'], 'load (load_0)')

    def test_questions_with_groups(self):
        factory = AppFactory()
        self._build_app_with_groups(factory)
        app = factory.app
        modules, errors = get_app_summary_formdata(app.domain, app)
        question_in_group = modules[0]['forms'][0]['questions'][1]['children'][0]
        self.assertEqual(question_in_group.value, '/data/demographics/age')
