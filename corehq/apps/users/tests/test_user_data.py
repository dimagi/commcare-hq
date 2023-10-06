from django.test import TestCase

from corehq.apps.custom_data_fields.models import (
    PROFILE_SLUG,
    CustomDataFieldsDefinition,
    CustomDataFieldsProfile,
    Field,
)
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView


class TestUserMetadata(TestCase):

    def setUp(self):
        self.domain = 'test-user-metadata'
        self.user = CommCareUser.create(
            domain=self.domain,
            username='birdman',
            password='***',
            created_by=None,
            created_via=None,
        )
        self.addCleanup(self.user.delete, self.domain, deleted_by=None)

    def test_user_data_not_allowed_in_create(self):
        message = "Do not access user_data directly, pass metadata argument to create."
        with self.assertRaisesMessage(ValueError, message):
            CommCareUser.create(self.domain, 'martha', 'bmfa', None, None, user_data={'country': 'Canada'})

    def test_metadata(self):
        user_data = self.user.get_user_data(self.domain)
        self.assertEqual(user_data['commcare_project'], self.domain)
        user_data.update({
            'cruise': 'control',
            'this': 'road',
        })
        # Normally you shouldn't use `user.user_data` directly - I'm demonstrating that it's updated
        self.assertEqual(self.user.user_data, {
            'commcare_project': self.domain,
            'cruise': 'control',
            'this': 'road',
        })
        del user_data['cruise']
        self.assertEqual(self.user.user_data, {
            'commcare_project': self.domain,
            'this': 'road',
        })
        user_data.update({'this': 'field'})
        self.assertEqual(self.user.user_data, {
            'commcare_project': self.domain,
            'this': 'field',
        })

    def test_metadata_with_profile(self):
        definition = CustomDataFieldsDefinition(domain=self.domain, field_type=UserFieldsView.field_type)
        definition.save()
        definition.set_fields([Field(slug='start')])
        definition.save()
        profile = CustomDataFieldsProfile(
            name='low',
            fields={'start': 'sometimes'},
            definition=definition,
        )
        profile.save()
        conflict_message = "metadata properties conflict with profile: start"

        # Custom user data profiles get their data added to metadata automatically for mobile users
        self.user.update_metadata({PROFILE_SLUG: profile.id})
        self.assertEqual(self.user.metadata, {
            'commcare_project': self.domain,
            PROFILE_SLUG: profile.id,
            'start': 'sometimes',
        })

        # Remove profile should remove it and related fields
        self.user.pop_metadata(PROFILE_SLUG)
        self.assertEqual(self.user.metadata, {
            'commcare_project': self.domain,
        })

        # Can't add profile that conflicts with existing data
        self.user.update_metadata({
            'start': 'never',
            'end': 'yesterday',
        })
        with self.assertRaisesMessage(ValueError, conflict_message):
            self.user.update_metadata({
                PROFILE_SLUG: profile.id,
            })

        # Can't add data that conflicts with existing profile
        self.user.pop_metadata('start')
        self.user.update_metadata({PROFILE_SLUG: profile.id})
        with self.assertRaisesMessage(ValueError, conflict_message):
            self.user.update_metadata({'start': 'never'})

        # Can't add both a profile and conflicting data
        self.user.pop_metadata(PROFILE_SLUG)
        with self.assertRaisesMessage(ValueError, conflict_message):
            self.user.update_metadata({
                PROFILE_SLUG: profile.id,
                'start': 'never',
            })

        # Custom user data profiles don't get populated for web users
        web_user = WebUser.create(None, "imogen", "*****", None, None)
        self.assertEqual(web_user.metadata, {
            'commcare_project': None,
        })
        web_user.update_metadata({PROFILE_SLUG: profile.id})
        self.assertEqual(web_user.metadata, {
            'commcare_project': None,
            PROFILE_SLUG: profile.id,
        })

        definition.delete()
        web_user.delete(self.domain, deleted_by=None)
