from django.test import SimpleTestCase

from corehq.apps.app_manager.models import (
    Application,
    ConditionalCaseUpdate,
    Module,
    PreloadAction,
    UpdateCaseAction,
)
from corehq.apps.app_manager.tests.util import (
    SuiteMixin,
    TestXmlMixin,
    patch_get_xform_resource_overrides,
)


@patch_get_xform_resource_overrides()
class SuiteUsercaseTest(SimpleTestCase, SuiteMixin):
    file_path = ('data', 'suite')

    def test_usercase_id_added_update(self, *args):
        app = Application.new_app('domain', "Untitled Application")

        module = app.add_module(Module.new_module("Untitled Module", None))
        module.case_type = 'child'

        form = app.new_form(0, "Untitled Form", None)
        form.xmlns = 'http://id_m1-f0'
        form.requires = 'case'
        form.actions.usercase_update = UpdateCaseAction(
            update={'name': ConditionalCaseUpdate(question_path='/data/question1')})
        form.actions.usercase_update.condition.type = 'always'

        self.assertXmlPartialEqual(self.get_xml('usercase_entry'), app.create_suite(), "./entry[1]")

    def test_usercase_id_added_preload(self, *args):
        app = Application.new_app('domain', "Untitled Application")

        module = app.add_module(Module.new_module("Untitled Module", None))
        module.case_type = 'child'

        form = app.new_form(0, "Untitled Form", None)
        form.xmlns = 'http://id_m1-f0'
        form.requires = 'case'
        form.actions.usercase_preload = PreloadAction(preload={'/data/question1': 'name'})
        form.actions.usercase_preload.condition.type = 'always'

        self.assertXmlPartialEqual(self.get_xml('usercase_entry'), app.create_suite(), "./entry[1]")
