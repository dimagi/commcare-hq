from django.core.cache import cache
from django.test import TestCase

from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import username_to_user_id


class TestUsernameToUserID(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestUsernameToUserID, cls).setUpClass()
        cls.user = CommCareUser.create('scale-domain', 'scale', 'dude')
        cache.clear()

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        cache.clear()
        super(TestUsernameToUserID, cls).tearDownClass()

    def test_username_to_user_id(self):
        user_id = username_to_user_id(self.user.username)
        self.assertEqual(user_id, self.user._id)

    def test_username_to_user_id_wrong_username(self):
        user_id = username_to_user_id('not-here')
        self.assertIsNone(user_id)
