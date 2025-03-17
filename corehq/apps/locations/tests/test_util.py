from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.commtrack.tests.util import TEST_LOCATION_TYPE, make_loc
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.apps.locations.util import does_location_type_have_users

from django.test import TestCase
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.es.client import manager
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
from corehq.util.es.testing import sync_users_to_es
from corehq.apps.locations.models import LocationType


@es_test(requires=[user_adapter])
class UtilTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super(UtilTest, cls).setUpClass()
        cls.domain = create_domain('locations-test')
        cls.loc = make_loc('loc', type='outlet', domain=cls.domain.name)
        cls.loc_type = LocationType.objects.get(name=TEST_LOCATION_TYPE)

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        super(UtilTest, cls).tearDownClass()

    def tearDown(self):
        delete_all_users()

    @sync_users_to_es()
    def test_loc_type_has_users(self):
        delete_all_users()
        user1 = WebUser.create(self.domain.name, 'web-user@example.com', '123', None, None)
        user2 = CommCareUser.create(self.domain.name, 'mobile-user', '123', None, None)
        user1.set_location(self.domain.name, self.loc)
        user2.set_location(self.loc)
        manager.index_refresh(user_adapter.index_name)
        self.assertTrue(does_location_type_have_users(self.loc_type))

    def _loc_type_does_not_have_user(self):
        self.assertFalse(does_location_type_have_users(self.loc_type))
