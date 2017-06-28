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


    def test_missing_ucrs(self):
        master_app = Application.new_app('domain', "Master Application")
        linked_app = Application.new_app('domain-2', "Linked Application")
        target_json = linked_app.to_json()
        module = master_app.add_module(ReportModule.new_module('Reports', None))
        module.report_configs = [
            ReportAppConfig(report_id='id', header={'en': 'CommBugz'}),
        ]
        with self.assertRaises(AppEditingError):
            overwrite_app(target_json, master_app, {})

    def test_static_ucrs(self):
        master_app = Application.new_app('domain', "Master Application")
        linked_app = Application.new_app('domain-2', "Linked Application")
        linked_app.save()
        target_json = linked_app.to_json()
        module = master_app.add_module(ReportModule.new_module('Reports', None))
        module.report_configs = [
            ReportAppConfig(report_id='id', header={'en': 'CommBugz'}),
        ]
        report_map = {'id': 'mapped_id'}
        overwrite_app(target_json, master_app, report_map)
        linked_app = Application.get(linked_app._id)
        self.assertEqual(linked_app.modules[0].report_configs[0].report_id, 'mapped_id')
