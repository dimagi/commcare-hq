from django.test import TestCase
from unittest.mock import patch
from corehq.apps.users.models import WebUser, CommCareUser, DomainMembership
from corehq.apps.locations.models import SQLLocation
from corehq.apps.groups.models import Group

from corehq.apps.users import cases
from corehq.apps.users.cases import get_owner_location_id


class TestGetEntityLocation(TestCase):
    def setUp(self):
        super().setUp()

        self.entities = {}

        def lookup(owner_id, support_deleted=False):
            return self.entities.get(owner_id, None)

        patcher = patch.object(cases, 'get_wrapped_owner', side_effect=lookup)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_retrieves_location_from_web_user(self):
        entity = WebUser(_id='1')
        entity.domain_memberships = [DomainMembership(domain='test-domain', location_id='123')]

        self.entities['1'] = entity

        self.assertEqual(get_owner_location_id(entity._id, 'test-domain'), '123')

    def test_retrieves_location_from_mobile_user(self):
        entity = CommCareUser(_id='2', domain='test-domain')
        entity.domain_membership = DomainMembership(domain='test-domain', location_id='123')

        self.entities['2'] = entity

        self.assertEqual(get_owner_location_id(entity._id, 'test-domain'), '123')

    def test_retrieves_location_from_location(self):
        entity = SQLLocation(location_id='123')
        self.entities['123'] = entity

        self.assertEqual(get_owner_location_id(entity.location_id, 'test-domain'), '123')

    def test_location_from_group_is_none(self):
        entity = Group(_id='3')

        self.entities['3'] = entity

        self.assertIsNone(get_owner_location_id(entity._id, 'test-domain'))
