from django.test import TestCase

from corehq.apps.custom_data_fields.models import (
    CustomDataFieldsDefinition,
    CustomDataFieldsProfile,
    Field,
    PROFILE_SLUG,
)
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView
from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.pillows.mappings.user_mapping import USER_INDEX, USER_INDEX_INFO
from corehq.pillows.user import transform_user_for_elasticsearch
from corehq.util.elastic import ensure_index_deleted
from pillowtop.es_utils import initialize_index_and_mapping


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
            "fields": {
                "corners": 5,
                "prefix": "penta",
            },
        }, {
            "id": self.profile3.id,
            "name": "three",
            "fields": {
                "corners": 3,
                "prefix": "tri",
            },
        }])

    def test_has_users_assigned(self):
        self.es = get_es_new()
        ensure_index_deleted(USER_INDEX)
        initialize_index_and_mapping(self.es, USER_INDEX_INFO)

        user = CommCareUser.create(self.domain, 'pentagon', '*****', None, None, metadata={
            PROFILE_SLUG: self.profile5.id,
        })
        self.addCleanup(user.delete, deleted_by=None)
        send_to_elasticsearch('users', transform_user_for_elasticsearch(user.to_json()))
        self.es.indices.refresh(USER_INDEX)

        self.assertFalse(self.profile3.has_users_assigned)
        self.assertTrue(self.profile5.has_users_assigned)

        ensure_index_deleted(USER_INDEX)
