from django.test import TestCase

from corehq.apps.custom_data_fields.models import (
    CustomDataFieldsDefinition,
    CustomDataFieldsProfile,
    Field,
)
from corehq.apps.custom_data_fields.edit_model import CustomDataModelMixin
from corehq.apps.domain.models import Domain
from corehq.apps.es.client import manager
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView
from corehq.util.es.testing import sync_users_to_es


class TestCustomDataFieldsProfile(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'a-domain'
        cls.domain_obj = Domain(name=cls.domain, default_timezone='UTC')
        cls.domain_obj.save()
        cls.definition = CustomDataFieldsDefinition(domain=cls.domain, field_type=UserFieldsView.field_type)
        cls.definition.save()
        cls.definition.set_fields([
            Field(
                slug='corners',
                is_required=True,
                label='Number of corners',
                regex='^[0-9]+$',
                regex_msg='This should be a number',
            ),
            Field(
                slug='prefix',
                is_required=False,
                label='Prefix',
                choices=['tri', 'tetra', 'penta'],
            ),
            Field(
                slug='color',
                is_required=False,
                label='Color',
            ),
        ])
        cls.definition.save()
        cls.custom_data_model = CustomDataModelMixin()
        cls.custom_data_model.domain = cls.domain

    @classmethod
    def tearDownClass(cls):
        cls.definition.delete()
        cls.domain_obj.delete()
        super().tearDownClass()

    def setUp(self):
        self.profile3, _ = CustomDataFieldsProfile.objects.update_or_create(
            name='three',
            fields={'corners': 3, 'prefix': 'tri'},
            definition=self.definition,
        )
        self.profile5, _ = CustomDataFieldsProfile.objects.update_or_create(
            name='five',
            fields={'corners': 5, 'prefix': 'penta'},
            definition=self.definition,
        )
        self.profiles = [self.profile3, self.profile5]

    def test_to_json(self):
        data = self.profile3.to_json()
        self.assertEqual(data, {
            "id": self.profile3.id,
            "name": "three",
            "upstream_id": None,
            "fields": {
                "corners": 3,
                "prefix": "tri",
            },
        })

    def test_get_profiles(self):
        profiles = [p.to_json() for p in self.definition.get_profiles()]
        self.assertEqual(profiles, [{
            "id": self.profile5.id,
            "name": "five",
            "upstream_id": None,
            "fields": {
                "corners": 5,
                "prefix": "penta",
            },
        }, {
            "id": self.profile3.id,
            "name": "three",
            "upstream_id": None,
            "fields": {
                "corners": 3,
                "prefix": "tri",
            },
        }])

    @es_test(requires=[user_adapter])
    @sync_users_to_es()
    def test_users_assigned(self):
        user = CommCareUser.create(self.domain, 'pentagon', '*****', None, None)
        user.get_user_data(self.domain).profile_id = self.profile5.id
        user.save()
        manager.index_refresh(user_adapter.index_name)
        self.addCleanup(user.delete, self.domain, deleted_by=None)

        self.assertFalse(self.profile3.has_users_assigned)
        self.assertItemsEqual([], self.profile3.user_ids_assigned())
        self.assertTrue(self.profile5.has_users_assigned)
        self.assertItemsEqual([user._id], self.profile5.user_ids_assigned())

    def test_profile_wont_delete_if_mobile_user_is_active(self):
        mobile_user = CommCareUser.create(self.domain, 'mobile_user', 'password', None, None)
        mobile_user.get_user_data(self.domain).profile_id = self.profile3.id
        mobile_user.save()
        self.addCleanup(mobile_user.delete, self.domain, deleted_by=None)
        # attempting to remove profile3
        updated_profile_list = [self.profile5.id]

        errors = self.custom_data_model.delete_eligible_profiles(self.profiles, updated_profile_list)
        self.assertTrue(errors)

        mobile_user.is_active = False
        mobile_user.save()
        errors = self.custom_data_model.delete_eligible_profiles(self.profiles, updated_profile_list)
        self.assertFalse(errors)
        self.assertEqual(CustomDataFieldsProfile.objects.filter(id=self.profile3.id).count(), 0)

    def test_profile_wont_delete_if_web_user_is_in_domain(self):
        web_user = WebUser.create(self.domain, 'web_user', 'password', None, None)
        web_user.get_user_data(self.domain).profile_id = self.profile5.id
        web_user.save()
        self.addCleanup(web_user.delete, self.domain, deleted_by=None)
        # attempting to remove profile5
        updated_profile_list = [self.profile3.id]

        errors = self.custom_data_model.delete_eligible_profiles(self.profiles, updated_profile_list)
        self.assertTrue(errors)

        web_user.delete_domain_membership(self.domain)
        web_user.save()
        errors = self.custom_data_model.delete_eligible_profiles(self.profiles, updated_profile_list)
        self.assertFalse(errors)
        self.assertEqual(CustomDataFieldsProfile.objects.filter(id=self.profile5.id).count(), 0)
