from django.test import TestCase
from corehq.apps.commtrack.tests.util import bootstrap_location_types
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser
from ..dbaccessors import (get_users_by_location_id, get_user_ids_by_location,
                           get_one_user_at_location, get_user_docs_by_location)
from .util import make_loc, delete_all_locations


class TestUsersByLocation(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.domain = create_domain('test-domain')
        bootstrap_location_types(cls.domain.name)

        def make_user(name, location):
            user = CommCareUser.create(cls.domain.name, name, 'password')
            user.set_location(location)
            return user

        cls.meereen = make_loc('meereen', type='outlet', domain=cls.domain.name)
        cls.pentos = make_loc('pentos', type='outlet', domain=cls.domain.name)

        cls.varys = make_user('Varys', cls.pentos)
        cls.tyrion = make_user('Tyrion', cls.meereen)
        cls.daenerys = make_user('Daenerys', cls.meereen)

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        delete_all_locations()

    def test_get_users_by_location_id(self):
        users = get_users_by_location_id(self.meereen._id)
        self.assertItemsEqual([u._id for u in users],
                              [self.tyrion._id, self.daenerys._id])

    def test_get_user_ids_by_location(self):
        user_ids = get_user_ids_by_location(self.meereen._id)
        self.assertItemsEqual(user_ids, [self.tyrion._id, self.daenerys._id])

    def test_get_one_user_at_location(self):
        user = get_one_user_at_location(self.meereen._id)
        self.assertIn(user._id, [self.tyrion._id, self.daenerys._id])

    def test_get_user_docs_by_location(self):
        users = get_user_docs_by_location(self.meereen._id)
        self.assertItemsEqual([u['doc'] for u in users],
                              [self.tyrion.to_json(), self.daenerys.to_json()])
