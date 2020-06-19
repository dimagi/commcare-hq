from django.core.cache import cache
from django.test import TestCase

from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import username_to_user_id, user_id_to_username, cached_user_id_to_user_display


class TestUsernameToUserID(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestUsernameToUserID, cls).setUpClass()
        cls.user = CommCareUser.create('scale-domain', 'scale', 'dude', None, None)
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


class TestUserIdToUsernameToUserName(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestUserIdToUsernameToUserName, cls).setUpClass()
        cls.user_without_name = CommCareUser.create('test-domain', 'no_name', 'a_secret', None, None)
        cls.user_with_first_name = CommCareUser.create('test-domain', 'first_name', 'a_secret', None, None,
                                                       first_name='Alice')
        cls.user_with_last_name = CommCareUser.create('test-domain', 'last_name', 'a_secret', None, None,
                                                      last_name='Jones')
        cls.user_with_full_name = CommCareUser.create('test-domain', 'full_name', 'a_secret', None, None,
                                                      first_name='Alice', last_name='Jones')
        cls.users = [
            cls.user_without_name,
            cls.user_with_first_name,
            cls.user_with_last_name,
            cls.user_with_full_name,
        ]
        cache.clear()

    @classmethod
    def tearDownClass(cls):
        for user in cls.users:
            user.delete()
        cache.clear()
        super(TestUserIdToUsernameToUserName, cls).tearDownClass()

    def test_user_id_to_username_no_names(self):
        for user in self.users:
            self.assertEqual(user.username, user_id_to_username(user.user_id))

    def test_user_id_to_username_with_names(self):
        self.assertEqual('no_name', user_id_to_username(self.user_without_name.user_id,
                                                        use_name_if_available=True))
        self.assertEqual('Alice', user_id_to_username(self.user_with_first_name.user_id,
                                                      use_name_if_available=True))
        self.assertEqual('Jones', user_id_to_username(self.user_with_last_name.user_id,
                                                      use_name_if_available=True))
        self.assertEqual('Alice Jones', user_id_to_username(self.user_with_full_name.user_id,
                                                            use_name_if_available=True))

    def test_cached_user_id_to_user_display(self):
        self.assertEqual('Alice', cached_user_id_to_user_display(self.user_with_first_name.user_id))
        self.assertEqual('Alice Jones', cached_user_id_to_user_display(self.user_with_full_name.user_id))
        self.user_with_first_name.first_name = 'Betty'
        self.user_with_first_name.save()
        self.assertEqual('Betty', user_id_to_username(self.user_with_first_name.user_id,
                                                      use_name_if_available=True))
        self.assertEqual('Alice', cached_user_id_to_user_display(self.user_with_first_name.user_id))
        self.assertEqual('Alice Jones', cached_user_id_to_user_display(self.user_with_full_name.user_id))
        # set username back because other tests rely on it
        self.user_with_first_name.first_name = 'Alice'
        self.user_with_first_name.save()
