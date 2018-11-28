from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase
from corehq.apps.commtrack.tests.util import bootstrap_location_types
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser, WebUser
from ..analytics import users_have_locations
from ..dbaccessors import (get_users_by_location_id, get_user_ids_by_location,
                           get_one_user_at_location, get_user_docs_by_location,
                           get_all_users_by_location, get_users_assigned_to_locations,
                           generate_user_ids_from_primary_location_ids_from_couch)
from .util import make_loc


class TestUsersByLocation(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestUsersByLocation, cls).setUpClass()
        cls.domain = 'test-domain'
        cls.domain_obj = create_domain(cls.domain)
        bootstrap_location_types(cls.domain)

        def make_user(name, location):
            user = CommCareUser.create(cls.domain, name, 'password')
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
            password='password'
        )
        cls.george.set_location(cls.domain, cls.meereen)

    @classmethod
    def tearDownClass(cls):
        cls.george.delete()
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
        other_user = CommCareUser.create(self.domain, 'other', 'password')
        users = get_users_assigned_to_locations(self.domain)
        self.assertItemsEqual(
            [u._id for u in users],
            [self.varys._id, self.tyrion._id, self.daenerys._id, self.george._id]
        )
        other_user.delete()

    def test_generate_user_ids_from_primary_location_ids_from_couch(self):
        self.assertItemsEqual(
            list(
                generate_user_ids_from_primary_location_ids_from_couch(
                    self.domain, [self.pentos.location_id, self.meereen.location_id]
                )
            ),
            [self.varys._id, self.tyrion._id, self.daenerys._id]
        )
