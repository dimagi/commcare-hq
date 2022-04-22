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
class SuiteUsercaseTest(SimpleTestCase, TestXmlMixin, SuiteMixin):
    file_path = ('data', 'suite')

    def test_usercase_id_added_update(self, *args):
        app = Application.new_app('domain', "Untitled Application")

        child_module = app.add_module(Module.new_module("Untitled Module", None))
        child_module.case_type = 'child'

        child_form = app.new_form(0, "Untitled Form", None)
        child_form.xmlns = 'http://id_m1-f0'
        child_form.requires = 'case'
        child_form.actions.usercase_update = UpdateCaseAction(
            update={'name': ConditionalCaseUpdate(question_path='/data/question1')})
        child_form.actions.usercase_update.condition.type = 'always'

        self.assertXmlPartialEqual(self.get_xml('usercase_entry'), app.create_suite(), "./entry[1]")

    def test_usercase_id_added_preload(self, *args):
        app = Application.new_app('domain', "Untitled Application")

        child_module = app.add_module(Module.new_module("Untitled Module", None))
        child_module.case_type = 'child'

        child_form = app.new_form(0, "Untitled Form", None)
        child_form.xmlns = 'http://id_m1-f0'
        child_form.requires = 'case'
        child_form.actions.usercase_preload = PreloadAction(preload={'/data/question1': 'name'})
        child_form.actions.usercase_preload.condition.type = 'always'

        self.assertXmlPartialEqual(self.get_xml('usercase_entry'), app.create_suite(), "./entry[1]")
