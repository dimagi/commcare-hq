from django.test import SimpleTestCase
from unittest.mock import patch

from corehq.apps.custom_data_fields.edit_entity import CustomDataEditor
from corehq.apps.custom_data_fields.models import Field

from corehq.apps.users.views.mobile.custom_data_fields import (
    UserFieldsView,
    WebUserFieldsView,
    CommcareUserFieldsView,
)
from corehq.apps.locations.views import LocationFieldsView


class FieldsViewMixin:

    def create_field(self, slug='test_field', label='Test Field', is_required=False, required_for=None,
                     choices=None, regex=None, regex_msg=None, upstream_id=None):
        if not required_for:
            required_for = []
        if not choices:
            choices = ["option1", "option2"]
        return Field(
            slug=slug,
            label=label,
            is_required=is_required,
            required_for=required_for,
            choices=choices,
            regex=regex,
            regex_msg=regex_msg,
            upstream_id=upstream_id,
        )

    _create_field = create_field


class TestCustomDataEditorFormFields(SimpleTestCase, FieldsViewMixin):
    @patch('corehq.apps.custom_data_fields.edit_entity.CustomDataEditor.init_form')
    def setUp(self, mock_init_form):
        self.domain = 'test-domain'
        self.web_user_editor = CustomDataEditor(WebUserFieldsView, self.domain)
        self.commcare_user_editor = CustomDataEditor(CommcareUserFieldsView, self.domain)
        self.location_editor = CustomDataEditor(LocationFieldsView, self.domain)

        self.web_user_field = self._create_field(is_required=True, required_for=[UserFieldsView.WEB_USER])
        self.commcare_user_field = self._create_field(is_required=True,
                                                    required_for=[UserFieldsView.COMMCARE_USER])

    def test_web_user_field_required_for_web_user(self):
        form_field = self.web_user_editor._make_field(self.web_user_field)
        self.assertTrue(form_field.required)

    def test_commcare_user_field_not_required_for_web_user(self):
        form_field = self.web_user_editor._make_field(self.commcare_user_field)
        self.assertFalse(form_field.required)

    def test_web_user_field_not_required_for_commcare_user(self):
        form_field = self.commcare_user_editor._make_field(self.web_user_field)
        self.assertFalse(form_field.required)

    def test_commcare_user_field_required_for_commcare_user(self):
        form_field = self.commcare_user_editor._make_field(self.commcare_user_field)
        self.assertTrue(form_field.required)

    def test_location_field_is_always_required(self):
        location_field = self._create_field(is_required=True)
        form_field = self.location_editor._make_field(location_field)
        self.assertTrue(form_field.required)
