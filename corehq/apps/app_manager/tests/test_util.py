from django.test.testcases import SimpleTestCase

import corehq.apps.app_manager.util as util
from corehq.apps.app_manager.models import (
    AdvancedModule,
    Application,
    LoadUpdateAction,
)


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
