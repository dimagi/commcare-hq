from django.test import SimpleTestCase
from unittest.mock import patch

from corehq.apps.custom_data_fields.edit_entity import CustomDataEditor
from corehq.apps.custom_data_fields.models import Field

from corehq.apps.users.views.mobile.custom_data_fields import WebUserFieldsView, CommcareUserFieldsView
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
    def setUp(self):
        self.domain = 'test-domain'

    @patch('corehq.apps.custom_data_fields.edit_entity.CustomDataEditor.init_form')
    def test_field_is_required(self, mock_init_form):
        web_user_editor = CustomDataEditor(WebUserFieldsView, self.domain)
        commcare_user_editor = CustomDataEditor(CommcareUserFieldsView, self.domain)

        web_user_field = self._create_field(is_required=True, required_for=['web_user'])
        commcare_user_field = self._create_field(is_required=True, required_for=['commcare_user'])

        form_field = web_user_editor._make_field(web_user_field)
        self.assertTrue(form_field.required)

        form_field = web_user_editor._make_field(commcare_user_field)
        self.assertFalse(form_field.required)

        form_field = commcare_user_editor._make_field(web_user_field)
        self.assertFalse(form_field.required)

        form_field = commcare_user_editor._make_field(commcare_user_field)
        self.assertTrue(form_field.required)

        location_editor = CustomDataEditor(LocationFieldsView, self.domain)
        location_field = self._create_field(is_required=True)
        form_field = location_editor._make_field(location_field)
        self.assertTrue(form_field.required)
