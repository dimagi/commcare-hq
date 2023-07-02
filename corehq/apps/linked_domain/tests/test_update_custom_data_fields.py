from unittest.mock import patch, PropertyMock
from corehq.apps.custom_data_fields.models import (
    CustomDataFieldsDefinition,
    CustomDataFieldsProfile,
    Field,
)
from corehq.apps.linked_domain.exceptions import DomainLinkError
from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedDomainTest
from corehq.apps.linked_domain.updates import update_custom_data_models, update_custom_data_models_impl
from corehq.apps.locations.views import LocationFieldsView
from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView

from django.test import TestCase


class TestUpdateCustomDataFields(BaseLinkedDomainTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.definition = CustomDataFieldsDefinition(domain=cls.domain, field_type=UserFieldsView.field_type)
        cls.definition.save()
        cls.definition.set_fields([
            Field(
                slug='has_legs',
                label='Has legs',
                choices=['yes', 'no'],
            ),
            Field(
                slug='can_swim',
                label='Can swim',
                choices=['yes', 'no'],
            ),
            Field(
                slug='color',
                label='Color',
            ),
        ])
        cls.definition.save()

        cls.coral_profile = CustomDataFieldsProfile(
            name='Coral',
            fields={'has_legs': 'no', 'can_swim': 'no'},
            definition=cls.definition,
        )
        cls.coral_profile.save()

        cls.fish_profile = CustomDataFieldsProfile(
            name='Fish',
            fields={'has_legs': 'no', 'can_swim': 'yes'},
            definition=cls.definition,
        )
        cls.fish_profile.save()

        # This test does not assign users to the profile, so mock this property out to avoid hitting elasticsearch
        patcher = patch.object(CustomDataFieldsProfile, 'has_users_assigned', new_callable=PropertyMock)
        mock_users_assigned = patcher.start()
        mock_users_assigned.return_value = False

        cls.addClassCleanup(patcher.stop)

    @classmethod
    def tearDownClass(cls):
        cls.definition.delete()
        super().tearDownClass()

    def test_update(self):
        # Initial update of linked domain
        update_custom_data_models(self.domain_link, limit_types=[UserFieldsView.field_type])
        model = CustomDataFieldsDefinition.objects.get(domain=self.linked_domain,
                                                       field_type=UserFieldsView.field_type)
        fields = model.get_fields()
        self.assertEqual(fields[0].slug, "has_legs")
        self.assertEqual(fields[0].label, "Has legs")
        self.assertEqual(fields[0].choices, ["yes", "no"])
        self.assertEqual(fields[1].slug, "can_swim")
        self.assertEqual(fields[2].slug, "color")

        profiles_by_name = {p.name: p for p in model.get_profiles()}
        self.assertEqual(profiles_by_name[self.coral_profile.name].fields, self.coral_profile.fields)
        self.assertEqual(profiles_by_name[self.fish_profile.name].fields, self.fish_profile.fields)

        # Add, update, and remove a profile
        lamprey_profile = CustomDataFieldsProfile(
            name='Lamprey',
            fields={'has_legs': 'no', 'can_swim': 'yes'},
            definition=self.definition,
        )
        lamprey_profile.save()
        self.fish_profile.fields = {
            'has_legs': 'no',
            'can_swim': 'no',
        }
        self.fish_profile.save()
        self.coral_profile.delete()

        update_custom_data_models(self.domain_link, limit_types=[UserFieldsView.field_type])
        model = CustomDataFieldsDefinition.objects.get(domain=self.linked_domain,
                                                       field_type=UserFieldsView.field_type)
        profiles_by_name = {p.name: p for p in model.get_profiles()}
        self.assertEqual(profiles_by_name[self.fish_profile.name].fields, self.fish_profile.fields)
        self.assertEqual(profiles_by_name[lamprey_profile.name].fields, lamprey_profile.fields)


class TestUpdateFields(TestCase):
    def test_can_update_user_fields(self):
        self._set_fields([Field(slug='a', label='label1', upstream_id='1')], UserFieldsView.field_type)

        updated_field = Field(id='1', slug='a', label='label2')
        update_definition = self._generate_update_definition_for_fields([updated_field], UserFieldsView.field_type)
        update_custom_data_models_impl(update_definition, self.domain)

        fields = self._get_fields(UserFieldsView.field_type)
        expected_field = Field(slug='a', label='label2', upstream_id='1')
        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0].to_dict(), expected_field.to_dict())

    def test_can_update_location_fields(self):
        self._set_fields([Field(slug='a', label='label1', upstream_id='1')], LocationFieldsView.field_type)

        updated_field = Field(id='1', slug='a', label='label2')
        update_definition = self._generate_update_definition_for_fields([updated_field],
            LocationFieldsView.field_type)
        update_custom_data_models_impl(update_definition, self.domain)

        fields = self._get_fields(LocationFieldsView.field_type)
        expected_field = Field(slug='a', label='label2', upstream_id='1')
        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0].to_dict(), expected_field.to_dict())

    def test_cannot_update_fields_with_the_same_slug(self):
        self._set_fields([Field(slug='a', label='label1')], UserFieldsView.field_type)

        updated_field = Field(id='1', slug='a', label='label2')
        update_definition = self._generate_update_definition_for_fields([updated_field], UserFieldsView.field_type)

        with self.assertRaisesMessage(DomainLinkError,
                'Failed to push the following Custom User Data Fields due to matching (same User Property)'
                ' unlinked Custom User Data Fields in this downstream project space: "a". Please edit the'
                ' Custom User Data Fields to resolve the matching or click "Push & Overwrite"'
                ' to overwrite and link the matching ones.'):
            update_custom_data_models_impl(update_definition, self.domain)

    def test_pull_error_message(self):
        self._set_fields([Field(slug='a', label='label1')], UserFieldsView.field_type)

        updated_field = Field(id='1', slug='a', label='label2')
        update_definition = self._generate_update_definition_for_fields([updated_field], UserFieldsView.field_type)

        with self.assertRaisesMessage(DomainLinkError,
                'Failed to sync the following Custom User Data Fields due to matching (same User Property)'
                ' unlinked Custom User Data Fields in this downstream project space: "a". Please edit the'
                ' Custom User Data Fields to resolve the matching or click "Sync & Overwrite"'
                ' to overwrite and link the matching ones.'):
            update_custom_data_models_impl(update_definition, self.domain, is_pull=True)

    def test_can_force_overwrite_fields_with_same_slug(self):
        self._set_fields([Field(slug='a', label='label1')], UserFieldsView.field_type)

        updated_field = Field(id='1', slug='a', label='label2')
        update_definition = self._generate_update_definition_for_fields([updated_field], UserFieldsView.field_type)

        update_custom_data_models_impl(update_definition, self.domain, overwrite=True)

        fields = self._get_fields(UserFieldsView.field_type)
        expected_field = Field(slug='a', label='label2', upstream_id='1')
        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0].to_dict(), expected_field.to_dict())

    def setUp(self):
        self.domain = 'test-domain'

    def _set_fields(self, fields, field_type):
        (definition, _) = CustomDataFieldsDefinition.objects.get_or_create(domain=self.domain,
            field_type=field_type)
        definition.set_fields(fields)

    def _get_fields(self, field_type):
        definition = CustomDataFieldsDefinition.objects.get(domain=self.domain, field_type=field_type)
        return definition.get_fields()

    def _generate_update_definition_for_fields(self, fields, field_type):
        fields_definition = {
            'fields': [self._get_field_dict(field) for field in fields]
        }

        return dict([(field_type, fields_definition)])

    def _get_field_dict(self, field):
        field_dict = field.to_dict()
        field_dict['id'] = field.id
        return field_dict


class TestUpdateProfiles(TestCase):
    def test_new_profile_is_created(self):
        fields = [Field(slug='a'), Field(slug='b'), Field(slug='c')]
        user_fields_definition = {
            'fields': [field_to_json(field) for field in fields],
            'profiles': [make_profile(id='1')],
        }
        update_json = {'UserFields': user_fields_definition}

        update_custom_data_models_impl(update_json, 'test-domain')

        definition = CustomDataFieldsDefinition.objects.get(domain='test-domain', field_type='UserFields')
        profiles = definition.get_profiles()
        self.assertEqual(len(profiles), 1)

        profile = profiles[0]
        self.assertEqual(profile.name, 'SyncedProfile1')
        self.assertEqual(profile.fields, "{'a': 'one'}")
        self.assertEqual(profile.upstream_id, '1')

    def test_previously_synced_profile_is_updated(self):
        downstream_fields = [Field(slug='a', upstream_id='1')]
        upstream_fields = [Field(id='1', slug='a')]
        existing_definition = CustomDataFieldsDefinition.objects.create(
            domain='test-domain', field_type='UserFields')
        existing_definition.set_fields(downstream_fields)
        existing_definition.save()
        make_existing_profile(existing_definition, upstream_id='1')

        user_fields_definition = {
            'fields': [field_to_json(field) for field in upstream_fields],
            'profiles': [make_profile(id='1')]
        }
        update_json = {'UserFields': user_fields_definition}

        update_custom_data_models_impl(update_json, 'test-domain')

        updated_definition = CustomDataFieldsDefinition.objects.get(domain='test-domain', field_type='UserFields')
        profiles = updated_definition.get_profiles()
        self.assertEqual(len(profiles), 1)

        profile = profiles[0]
        self.assertEqual(profile.fields, "{'a': 'one'}")
        self.assertEqual(profile.upstream_id, '1')

    def test_existing_profile_raises_error(self):
        downstream_fields = [Field(slug='a', upstream_id='1')]
        upstream_fields = [Field(id='1', slug='a')]
        existing_definition = CustomDataFieldsDefinition.objects.create(
            domain='test-domain', field_type='UserFields'
        )
        existing_definition.set_fields(downstream_fields)
        existing_definition.save()
        make_existing_profile(existing_definition, upstream_id=None)

        user_fields_definition = {
            'fields': [field_to_json(field) for field in upstream_fields],
            'profiles': [make_profile(id='1')]
        }
        update_json = {'UserFields': user_fields_definition}

        with self.assertRaisesMessage(DomainLinkError,
                'Failed to push the following Custom User Data Fields Profiles due to matching (same User Profile)'
                ' unlinked Custom User Data Fields Profiles in this downstream project space: "SyncedProfile1".'
                ' Please edit the Custom User Data Fields Profiles to resolve the matching or click'
                ' "Push & Overwrite" to overwrite and link the matching ones.'):
            update_custom_data_models_impl(update_json, 'test-domain')

    def test_pull_error_message(self):
        downstream_fields = [Field(slug='a', upstream_id='1')]
        upstream_fields = [Field(id='1', slug='a')]
        existing_definition = CustomDataFieldsDefinition.objects.create(
            domain='test-domain', field_type='UserFields'
        )
        existing_definition.set_fields(downstream_fields)
        existing_definition.save()
        make_existing_profile(existing_definition, upstream_id=None)

        user_fields_definition = {
            'fields': [field_to_json(field) for field in upstream_fields],
            'profiles': [make_profile(id='1')]
        }
        update_json = {'UserFields': user_fields_definition}

        with self.assertRaisesMessage(DomainLinkError,
                'Failed to sync the following Custom User Data Fields Profiles due to matching (same User Profile)'
                ' unlinked Custom User Data Fields Profiles in this downstream project space: "SyncedProfile1".'
                ' Please edit the Custom User Data Fields Profiles to resolve the matching or click'
                ' "Sync & Overwrite" to overwrite and link the matching ones.'):
            update_custom_data_models_impl(update_json, 'test-domain', is_pull=True)

    def test_can_force_overwrite_existing_profile(self):
        downstream_fields = [Field(slug='a', upstream_id='1')]
        upstream_fields = [Field(id='1', slug='a')]
        existing_definition = CustomDataFieldsDefinition.objects.create(
            domain='test-domain', field_type='UserFields')
        existing_definition.set_fields(downstream_fields)
        existing_definition.save()
        make_existing_profile(existing_definition, upstream_id=None)

        user_fields_definition = {
            'fields': [field_to_json(field) for field in upstream_fields],
            'profiles': [make_profile(id='1')]
        }
        update_json = {'UserFields': user_fields_definition}

        with patch.object(
                CustomDataFieldsProfile, 'has_users_assigned', new_callable=PropertyMock) as mock_users_assigned:
            mock_users_assigned.return_value = False
            update_custom_data_models_impl(update_json, 'test-domain', overwrite=True)

        updated_definition = CustomDataFieldsDefinition.objects.get(domain='test-domain', field_type='UserFields')
        profiles = updated_definition.get_profiles()
        self.assertEqual(len(profiles), 1)

        profile = profiles[0]
        self.assertEqual(profile.fields, "{'a': 'one'}")
        self.assertEqual(profile.upstream_id, '1')

    def test_cannot_force_ovewrite_existing_profile_if_in_use(self):
        downstream_fields = [Field(slug='a', upstream_id='1')]
        upstream_fields = [Field(id='1', slug='a')]
        existing_definition = CustomDataFieldsDefinition.objects.create(
            domain='test-domain', field_type='UserFields')
        existing_definition.set_fields(downstream_fields)
        existing_definition.save()
        make_existing_profile(existing_definition, upstream_id=None)

        user_fields_definition = {
            'fields': [field_to_json(field) for field in upstream_fields],
            'profiles': [make_profile(id='1')]
        }
        update_json = {'UserFields': user_fields_definition}

        with self.assertRaisesMessage(DomainLinkError,
                'Cannot overwrite profiles, as the following profiles are still in use: SyncedProfile1'), \
                patch.object(
                CustomDataFieldsProfile, 'has_users_assigned', new_callable=PropertyMock) as mock_users_assigned:
            mock_users_assigned.return_value = True
            update_custom_data_models_impl(update_json, 'test-domain', overwrite=True)

    def test_can_remove_profile(self):
        downstream_fields = [Field(slug='a', upstream_id='1')]
        upstream_fields = [Field(id='1', slug='a')]
        existing_definition = CustomDataFieldsDefinition.objects.create(
            domain='test-domain', field_type='UserFields'
        )
        existing_definition.set_fields(downstream_fields)
        existing_definition.save()
        make_existing_profile(existing_definition, upstream_id='1')

        user_fields_definition = {
            'fields': [field_to_json(field) for field in upstream_fields],
            # No Profiles
        }
        update_json = {'UserFields': user_fields_definition}

        with patch.object(
                CustomDataFieldsProfile, 'has_users_assigned', new_callable=PropertyMock) as mock_users_assigned:
            mock_users_assigned.return_value = False
            update_custom_data_models_impl(update_json, 'test-domain')

        updated_definition = CustomDataFieldsDefinition.objects.get(domain='test-domain', field_type='UserFields')
        self.assertEqual(updated_definition.get_profiles(), [])

    def test_removing_used_profile_does_not_delete_the_profile(self):
        # NOTE: Initially I tried to have profiles actually assigned to users,
        # but ran into some issues I believe due to how the test environment interacts with Elasticsearch.
        # Due to this, I'm just faking out 'has_users_assigned' to always believe that the profile is in use.

        # create a profile
        downstream_fields = [Field(slug='a', upstream_id='1')]
        upstream_fields = [Field(id='1', slug='a')]
        existing_definition = CustomDataFieldsDefinition.objects.create(
            domain='test-domain', field_type='UserFields')
        existing_definition.save()
        existing_definition.set_fields(downstream_fields)
        existing_definition.save()
        make_existing_profile(existing_definition, upstream_id='1')

        # the new definition should try to delete the used profile
        user_fields_definition = {
            'fields': [field_to_json(field) for field in upstream_fields],
            # No Profiles
        }
        update_json = {'UserFields': user_fields_definition}

        with patch.object(
                CustomDataFieldsProfile, 'has_users_assigned', new_callable=PropertyMock) as mock_users_assigned:
            mock_users_assigned.return_value = True
            update_custom_data_models_impl(update_json, 'test-domain')

        updated_definition = CustomDataFieldsDefinition.objects.get(domain='test-domain', field_type='UserFields')
        updated_profiles = updated_definition.get_profiles()
        self.assertEqual(len(updated_profiles), 1)
        self.assertEqual(updated_profiles[0].name, 'SyncedProfile1')


def field_to_json(field):
    return {
        'id': field.id,
        'slug': field.slug,
        'is_required': field.is_required,
        'label': field.label,
        'choices': field.choices,
        'regex': field.regex,
        'regex_msg': field.regex_msg,
    }


def make_profile(id):
    return {
        'id': id,
        'name': 'SyncedProfile1',
        'fields': "{'a': 'one'}",
    }


def make_existing_profile(definition, upstream_id=None):
    return CustomDataFieldsProfile.objects.create(
        name='SyncedProfile1', fields={'a': 'two'}, upstream_id=upstream_id, definition=definition)
