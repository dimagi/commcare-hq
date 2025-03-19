from unittest import mock
from django.test import TestCase

from corehq.apps.commtrack.tests.util import bootstrap_location_types
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.tests.utils import es_test
from corehq.apps.users.models import CommCareUser, WebUser

from corehq.util.es.testing import sync_users_to_es
from corehq.apps.es.users import user_adapter
from corehq.apps.es.client import manager

from corehq.apps.domain.models import Domain

from ..analytics import users_have_locations
from ..dbaccessors import (
    get_all_users_by_location,
    get_one_user_at_location,
    get_user_docs_by_location,
    get_user_ids_by_location,
    get_users_assigned_to_locations,
    get_users_by_location_id,
    get_users_location_ids,
    user_ids_at_locations,
    mobile_user_ids_at_locations,
)
from .util import make_loc, delete_all_locations
from ..dbaccessors import get_filtered_locations_count


@es_test(requires=[user_adapter], setup_class=True)
class TestUsersByLocation(TestCase):

    @classmethod
    @sync_users_to_es()
    @mock.patch('corehq.apps.groups.dbaccessors.get_group_id_name_map_by_user', mock.Mock(return_value=[]))
    def setUpClass(cls):
        super(TestUsersByLocation, cls).setUpClass()
        cls.domain = 'test-domain'
        cls.domain_obj = create_domain(cls.domain)
        bootstrap_location_types(cls.domain)

        def make_user(name, location):
            user = CommCareUser.create(cls.domain, name, 'password', None, None)
            user.set_location(location)
            return user

        cls.meereen = make_loc('meereen', type='outlet', domain=cls.domain)
        cls.pentos = make_loc('pentos', type='outlet', domain=cls.domain)

        cls.varys = make_user('Varys', cls.pentos)
        cls.tyrion = make_user('Tyrion', cls.meereen)
        cls.daenerys = make_user('Daenerys', cls.meereen)

        cls.george = WebUser.create(
            cls.domain,
            username="George RR Martin",
            password='password',
            created_by=None,
            created_via=None,
        )
        cls.george.set_location(cls.domain, cls.meereen)

        manager.index_refresh(user_adapter.index_name)

    @classmethod
    def tearDownClass(cls):
        cls.george.delete(cls.domain, deleted_by=None)
        cls.domain_obj.delete()
        super(TestUsersByLocation, cls).tearDownClass()

    def test_get_users_by_location_id(self):
        users = get_users_by_location_id(self.domain, self.meereen._id)
        self.assertItemsEqual([u._id for u in users],
                              [self.tyrion._id, self.daenerys._id])

    def test_get_user_ids_by_location(self):
        user_ids = get_user_ids_by_location(self.domain, self.meereen._id)
        self.assertItemsEqual(user_ids, [self.tyrion._id, self.daenerys._id])

    def test_get_one_user_at_location(self):
        user = get_one_user_at_location(self.domain, self.meereen._id)
        self.assertIn(user._id, [self.tyrion._id, self.daenerys._id])

    def test_get_user_docs_by_location(self):
        users = get_user_docs_by_location(self.domain, self.meereen._id)
        self.assertItemsEqual([u['doc'] for u in users],
                              [self.tyrion.to_json(), self.daenerys.to_json()])

    def test_get_all_users_by_location(self):
        users = get_all_users_by_location(self.domain, self.meereen._id)
        self.assertItemsEqual(
            [u._id for u in users],
            [self.tyrion._id, self.daenerys._id, self.george._id]
        )

    def test_users_have_locations(self):
        self.assertTrue(users_have_locations(self.domain))
        domain2 = create_domain('no-locations')
        self.assertFalse(users_have_locations('no-locations'))
        domain2.delete()

    def test_get_users_assigned_to_locations(self):
        other_user = CommCareUser.create(self.domain, 'other', 'password', None, None)
        users = get_users_assigned_to_locations(self.domain)
        self.assertItemsEqual(
            [u._id for u in users],
            [self.varys._id, self.tyrion._id, self.daenerys._id, self.george._id]
        )
        other_user.delete(self.domain, deleted_by=None)

    def test_get_users_location_ids(self):
        self.assertItemsEqual(
            get_users_location_ids(self.domain, [self.varys._id, self.tyrion._id]),
            [self.meereen._id, self.pentos._id]
        )

    def test_user_ids_at_locations(self):
        self.assertItemsEqual(
            mobile_user_ids_at_locations([self.meereen._id]),
            [self.daenerys._id, self.tyrion._id]
        )

    def test_all_user_ids_at_locations(self):
        self.assertItemsEqual(
            user_ids_at_locations([self.meereen._id]),
            [self.daenerys._id, self.tyrion._id, self.george._id]
        )


class TestFilteredLocationsCount(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ccdomain = Domain(name='cc_user_domain')
        cls.ccdomain.save()

        bootstrap_location_types(cls.ccdomain.name)
        cls.loc1 = make_loc('spain', domain=cls.ccdomain.name, type='state')
        cls.loc2 = make_loc('madagascar', domain=cls.ccdomain.name, parent=cls.loc1, type='district')

    @classmethod
    def tearDownClass(cls):
        delete_all_locations()
        cls.ccdomain.delete()
        super().tearDownClass()

    def test_location_filter_location_id(self):
        filters = {}
        self.assertEqual(get_filtered_locations_count(
            self.ccdomain.name,
            root_location_ids=[self.loc1._id],
            **filters), 2)

        filters = {}
        self.assertEqual(get_filtered_locations_count(
            self.ccdomain.name,
            root_location_ids=[self.loc2._id],
            **filters), 1)

    def test_location_filter_active_status(self):
        filters = {'is_archived': True}
        self.assertEqual(get_filtered_locations_count(self.ccdomain.name, **filters), 0)

        self.loc2.archive()
        filters = {'is_archived': False}
        self.assertEqual(get_filtered_locations_count(
            self.ccdomain.name,
            root_location_ids=[self.loc1._id],
            **filters), 1)

        filters = {'is_archived': True}
        self.assertEqual(get_filtered_locations_count(self.ccdomain.name, **filters), 1)
