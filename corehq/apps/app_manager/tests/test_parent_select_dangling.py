"""
Tests for the case list form options and settings page of a module that
uses "Select Parent First", including when the parent module has been
deleted.
"""
from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import reverse

from corehq import toggles
from corehq.apps.app_manager.models import Application, Module
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.test_views import ViewsBase
from corehq.apps.app_manager.tests.util import get_simple_form
from corehq.apps.app_manager.views.modules import (
    _case_list_form_options,
    get_parent_select_followup_forms,
)
from corehq.apps.builds.models import BuildSpec
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


class TestParentSelectFollowupForms(SimpleTestCase):

    def test_followup_forms_of_parent_module(self):
        app, parent_module, child_module = _make_parent_child_app()
        forms = get_parent_select_followup_forms(app, child_module)
        assert [f.unique_id for f in forms] == [parent_module.get_form(0).unique_id]

    def test_parent_module_deleted(self):
        app, parent_module, child_module = _make_parent_child_app()
        # same end state as Application.delete_module, without the Couch undo record
        del app.modules[parent_module.id]
        assert child_module.parent_select.module_id not in {m.unique_id for m in app.get_modules()}

        assert get_parent_select_followup_forms(app, child_module) == []

    def test_parent_select_inactive(self):
        app, parent_module, child_module = _make_parent_child_app()
        child_module.parent_select.active = False
        assert get_parent_select_followup_forms(app, child_module) == []


@patch('corehq.apps.app_manager.models.forms.validate_xform', return_value=None)
class TestModuleViewWithDeletedParentSelectModule(ViewsBase):
    domain = 'test-deleted-parent-select'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.app = Application.new_app(cls.domain, "ParentSelectApp")
        cls.app.build_spec = BuildSpec.from_string('2.7.0/latest')
        parent = cls.app.add_module(Module.new_module("Mothers", "en"))
        parent.case_type = 'mother'
        cls.app.new_form(parent.id, "Follow up mother", "en", attachment=get_simple_form(xmlns='xmlns-0'))
        child = cls.app.add_module(Module.new_module("Children", "en"))
        child.case_type = 'child'
        cls.app.new_form(child.id, "Follow up child", "en", attachment=get_simple_form(xmlns='xmlns-1'))
        for form in cls.app.get_forms():
            form.requires = 'case'
        child.parent_select.active = True
        child.parent_select.module_id = parent.unique_id
        child.parent_select.relationship = 'parent'
        cls.app.delete_module(parent.unique_id)
        cls.app.save()
        cls.child = child

    def setUp(self):
        self.client.login(username=self.username, password=self.password)

    @classmethod
    def tearDownClass(cls):
        cls.app.delete()
        super().tearDownClass()

    def _get_module_page(self):
        url = reverse('view_module', kwargs={
            'domain': self.domain,
            'app_id': self.app.id,
            'module_unique_id': self.child.unique_id,
        })
        return self.client.get(url)

    def test_page_renders_with_followup_forms_toggle(self, _):
        with flag_enabled('FOLLOWUP_FORMS_AS_CASE_LIST_FORM'):
            response = self._get_module_page()
        assert response.status_code == 200
        assert response.context['case_list_form_options']['options'] == {}

    def test_page_renders_without_followup_forms_toggle(self, _):
        assert not toggles.FOLLOWUP_FORMS_AS_CASE_LIST_FORM.enabled(self.domain)
        response = self._get_module_page()
        assert response.status_code == 200
