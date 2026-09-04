"""
Tests for the case list form options of a module that uses
"Select Parent First".
"""
from django.test import SimpleTestCase

from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.views.modules import _case_list_form_options
from corehq.util.test_utils import flag_enabled


def _make_parent_child_app(domain='parent-select-domain'):
    factory = AppFactory(domain=domain, build_version='2.53.0')
    parent_module, parent_form = factory.new_basic_module('mothers', 'mother')
    factory.form_requires_case(parent_form)
    child_module, child_form = factory.new_basic_module('children', 'child')
    factory.form_requires_case(child_form)

    child_module.parent_select.active = True
    child_module.parent_select.module_id = parent_module.unique_id
    child_module.parent_select.relationship = 'parent'
    return factory.app, parent_module, child_module


class TestCaseListFormOptions(SimpleTestCase):

    def test_parent_followup_forms_offered_with_toggle(self):
        app, parent_module, child_module = _make_parent_child_app()
        with flag_enabled('FOLLOWUP_FORMS_AS_CASE_LIST_FORM'):
            options = _case_list_form_options(app, child_module)['options']
        parent_form = parent_module.get_form(0)
        assert list(options) == [parent_form.unique_id]
        assert options[parent_form.unique_id]['is_registration_form'] is False

    def test_parent_followup_forms_not_offered_without_toggle(self):
        app, parent_module, child_module = _make_parent_child_app()
        assert _case_list_form_options(app, child_module)['options'] == {}
