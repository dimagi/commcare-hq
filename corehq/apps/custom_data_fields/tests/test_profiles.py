from django.test import TestCase

from corehq.apps.custom_data_fields.models import (
    PROFILE_SLUG,
    CustomDataFieldsDefinition,
    CustomDataFieldsProfile,
    Field,
)
from corehq.apps.es.client import manager
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView
from corehq.util.es.testing import sync_users_to_es


class TestCustomDataFieldsProfile(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'a-domain'
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

        cls.profile3 = CustomDataFieldsProfile(
            name='three',
            fields={'corners': 3, 'prefix': 'tri'},
            definition=cls.definition,
        )
        cls.profile3.save()

        cls.profile5 = CustomDataFieldsProfile(
            name='five',
            fields={'corners': 5, 'prefix': 'penta'},
            definition=cls.definition,
        )
        cls.profile5.save()

    @classmethod
    def tearDownClass(cls):
        cls.definition.delete()
        super().tearDownClass()

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
        self.assertEqual([], self.profile3.user_ids_assigned())
        self.assertTrue(self.profile5.has_users_assigned)
        self.assertEqual([user._id], self.profile5.user_ids_assigned())
