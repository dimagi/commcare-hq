from django.test.testcases import SimpleTestCase, TestCase

import corehq.apps.app_manager.util as util
from corehq.apps.app_manager.exceptions import AppEditingError
from corehq.apps.app_manager.models import (
    AdvancedModule,
    Application,
    LoadUpdateAction,
    ReportModule, ReportAppConfig)
from corehq.apps.app_manager.views.utils import overwrite_app


class TestGetFormData(SimpleTestCase):

    def test_advanced_form_get_action_type(self):
        app = Application.new_app('domain', "Untitled Application")

        parent_module = app.add_module(AdvancedModule.new_module('parent', None))
        parent_module.case_type = 'parent'
        parent_module.unique_id = 'id_parent_module'

        form = app.new_form(0, "Untitled Form", None)
        form.xmlns = 'http://id_m1-f0'
        form.actions.load_update_cases.append(LoadUpdateAction(case_type="clinic", case_tag='load_0'))

        modules, errors = util.get_form_data('domain', app)
        self.assertEqual(modules[0]['forms'][0]['action_type'], 'load (load_0)')


class TestOverwriteApp(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestOverwriteApp, cls).setUpClass()
        cls.master_app = Application.new_app('domain', "Master Application")
        cls.linked_app = Application.new_app('domain-2', "Linked Application")
        module = cls.master_app.add_module(ReportModule.new_module('Reports', None))
        module.report_configs = [
            ReportAppConfig(report_id='id', header={'en': 'CommBugz'}),
        ]
        cls.linked_app.save()
        cls.target_json = cls.linked_app.to_json()

    def test_missing_ucrs(self):
        with self.assertRaises(AppEditingError):
            overwrite_app(self.target_json, self.master_app, {})

    def test_report_mapping(self):
        report_map = {'id': 'mapped_id'}
        overwrite_app(self.target_json, self.master_app, report_map)
        linked_app = Application.get(self.linked_app._id)
        self.assertEqual(linked_app.modules[0].report_configs[0].report_id, 'mapped_id')
