import json
from django.test import RequestFactory
from django.views.generic import View
from django.contrib.messages import get_messages
from django.contrib.messages.storage import default_storage
from django.test import TestCase, SimpleTestCase
from corehq.apps.custom_data_fields.models import (
    CustomDataFieldsDefinition,
    CustomDataFieldsProfile,
    Field,
)
from corehq.apps.custom_data_fields.edit_model import CustomDataFieldsForm, CustomDataModelMixin


class FieldsView(CustomDataModelMixin, View):
    field_type = 'UserFields'
    _show_profiles = True
    domain = None
    form_data = None
    has_edit_permission = True

    def __init__(self, domain, fields=None, profiles=None, has_edit_permission=True):
        self.domain = domain
        self.fields = fields or []
        self.profiles = profiles or []
        self.has_edit_permission = has_edit_permission

    @property
    def form(self):
        fields_json = json.dumps([field.to_dict() for field in self.fields])
        profiles_json = json.dumps([profile.to_json() for profile in self.profiles])
        form = CustomDataFieldsForm({
            'data_fields': fields_json,
            'profiles': profiles_json,
        })
        form.is_valid()
        return form

    def can_edit_linked_data(self):
        return self.has_edit_permission

    def get(self, request, *args, **kwargs):
        return request  # just hacked out to allow access to the request/messages


def fields_are_equal(left, right):
    return left.to_dict() == right.to_dict()


class FieldsViewMixin:

    def create_field(self, slug='test_field', label='Test Field', is_required=False, choices=[], regex=None,
            regex_msg=None, upstream_id=None):
        return Field(
            slug=slug,
            label=label,
            is_required=is_required,
            choices=choices,
            regex=regex,
            regex_msg=regex_msg,
            upstream_id=upstream_id,
        )

    _create_field = create_field


class TestEditModel(FieldsViewMixin, TestCase):
    domain = 'test-domain'

    def test_saves_custom_fields(self):
        field = self._create_field()

        view = FieldsView(domain=self.domain, fields=[field])
        view.save_custom_fields()

        fields = view.get_definition().get_fields()
        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0].to_dict(), field.to_dict())

    def test_overwrites_custom_fields(self):
        existing_field = self._create_field(slug='ExistingField')
        self._create_initial_fields([existing_field])
        new_field = self._create_field(slug='NewField')

        view = FieldsView(domain='test-domain', fields=[new_field])
        view.save_custom_fields()

        fields = view.get_definition().get_fields()
        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0].slug, 'NewField')

    def test_fails_to_overwrite_without_proper_role(self):
        existing_field = self._create_field(slug='ExistingField', upstream_id='1', is_required=False)
        self._create_initial_fields([existing_field])
        modified_field = self._create_field(slug='ExistingField', upstream_id='1', is_required=True)

        view = FieldsView(domain=self.domain, fields=[modified_field], has_edit_permission=False)
        request = self._create_request()
        response = view.post(request)

        messages = list(get_messages(response))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]),
            "Could not update 'ExistingField'. You do not have the appropriate role")

    def _create_initial_fields(self, fields):
        definition = CustomDataFieldsDefinition.objects.create(field_type='UserFields', domain=self.domain)
        definition.set_fields(fields)

    def _create_request(self):
        request = RequestFactory().post('/', {})
        request._messages = default_storage(request)
        return request


class TestValidateIncomingFields(FieldsViewMixin, SimpleTestCase):
    def test_no_conflicts_produces_no_errors(self):
        existing_fields = [self.create_field(is_required=False)]
        new_fields = [self.create_field(is_required=True)]

        errors = FieldsView.validate_incoming_fields(existing_fields, new_fields)
        self.assertEqual(errors, [])

    def test_new_entry_produces_no_errors(self):
        existing_fields = []
        new_fields = [self.create_field()]

        errors = FieldsView.validate_incoming_fields(existing_fields, new_fields)
        self.assertEqual(errors, [])

    def test_deletion_produces_no_errors(self):
        existing_fields = [self.create_field()]
        new_fields = []

        errors = FieldsView.validate_incoming_fields(existing_fields, new_fields)
        self.assertEqual(errors, [])

    def test_sync_turned_on_produces_error(self):
        existing_fields = [self.create_field(slug='local_field', upstream_id=None)]
        new_fields = [self.create_field(slug='local_field', upstream_id='1')]

        errors = FieldsView.validate_incoming_fields(existing_fields, new_fields)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0], "Could not update 'local_field'. Synced data cannot be created this way")

    def test_sync_turned_off_produces_error(self):
        existing_fields = [self.create_field(slug='managed_field', upstream_id='1')]
        new_fields = [self.create_field(slug='managed_field', upstream_id=None)]

        errors = FieldsView.validate_incoming_fields(existing_fields, new_fields)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0], "Unable to remove synced fields. You do not have the appropriate role")

    def test_can_update_synced_data_with_permission(self):
        existing_fields = [self.create_field(slug='managed_field', upstream_id='1', is_required=True)]
        new_fields = [self.create_field(slug='managed_field', upstream_id='1', is_required=False)]

        errors = FieldsView.validate_incoming_fields(existing_fields, new_fields, can_edit_linked_data=True)
        self.assertEqual(errors, [])

    def test_updating_synced_data_without_permission_produces_error(self):
        existing_fields = [self.create_field(slug='managed_field', upstream_id='1', is_required=True)]
        new_fields = [self.create_field(slug='managed_field', upstream_id='1', is_required=False)]

        errors = FieldsView.validate_incoming_fields(existing_fields, new_fields, can_edit_linked_data=False)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0], "Could not update 'managed_field'. You do not have the appropriate role")

    def test_deleting_synced_data_without_permission_produces_error(self):
        existing_fields = [self.create_field(slug='managed_field', upstream_id='1')]
        new_fields = []

        errors = FieldsView.validate_incoming_fields(existing_fields, new_fields, can_edit_linked_data=False)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0], "Unable to remove synced fields. You do not have the appropriate role")

    def test_cannot_create_new_synced_data(self):
        existing_fields = []
        new_fields = [self.create_field(slug='managed_field', upstream_id='1')]

        errors = FieldsView.validate_incoming_fields(existing_fields, new_fields, can_edit_linked_data=True)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0], "Could not update 'managed_field'. Synced data cannot be created this way")

    def test_synced_slugs_can_change(self):
        existing_fields = [self.create_field(slug='old_name', upstream_id='1')]
        new_fields = [self.create_field(slug='new_name', upstream_id='1')]

        errors = FieldsView.validate_incoming_fields(existing_fields, new_fields, can_edit_linked_data=True)
        self.assertEqual(errors, [])

    def test_duplicate_upstream_ids_cause_error(self):
        existing_fields = [self.create_field(slug='managed_field', upstream_id='1')]
        new_fields = [
            self.create_field(slug='one', upstream_id='1'),
            self.create_field(slug='two', upstream_id='1')
        ]

        errors = FieldsView.validate_incoming_fields(existing_fields, new_fields, can_edit_linked_data=True)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0], "Could not update 'two'. Synced data cannot be created this way")


class TestCustomDataModelValidation(FieldsViewMixin, SimpleTestCase):

    def test_error_in_data_fiels_does_not_cause_error_in_profiles(self):
        view = FieldsView(
            "test",
            fields=[
                self.create_field(slug='one', label='one'),
                self.create_field(slug='two', label=''),
            ],
            profiles=[CustomDataFieldsProfile(name="OneProfile", fields={"one": "one"})],
        )
        self.assertDictEqual(
            view.form.errors,
            {"data_fields": ["A label is required for each field."]},
        )


class TestCustomDataFieldsForm(FieldsViewMixin, SimpleTestCase):
    def test_valid(self):
        fields = [self.create_field(slug='one')]
        profiles = [CustomDataFieldsProfile(name='profile', fields={'one': 'one'})]
        form = self._create_form(fields, profiles)

        self.assertTrue(form.is_valid())

    def test_can_assign_empty_profile_values_to_optional_fields(self):
        fields = [self.create_field(slug='one', is_required=False)]
        profiles = [CustomDataFieldsProfile(name='profile', fields={'one': ''})]
        form = self._create_form(fields, profiles)

        self.assertTrue(form.is_valid())

    def test_cannot_assign_empty_profile_values_to_required_fields(self):
        fields = [self.create_field(slug='one', is_required=True)]
        profiles = [CustomDataFieldsProfile(name='profile', fields={'one': ''})]
        form = self._create_form(fields, profiles)

        self.assertFalse(form.is_valid())

    def _create_form(self, fields, profiles):
        fields_json = json.dumps([field.to_dict() for field in fields])
        profiles_json = json.dumps([profile.to_json() for profile in profiles])
        return CustomDataFieldsForm({
            'data_fields': fields_json,
            'profiles': profiles_json
        })
