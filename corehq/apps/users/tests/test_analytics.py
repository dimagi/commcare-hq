from django.test import TestCase
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.analytics import update_analytics_indexes, get_count_of_active_commcare_users_in_domain, \
    get_count_of_inactive_commcare_users_in_domain, get_active_commcare_users_in_domain, \
    get_inactive_commcare_users_in_domain
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.users.models import CommCareUser, WebUser


class UserAnalyticsTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(UserAnalyticsTest, cls).setUpClass()
        delete_all_users()
        cls.domain = create_domain('test')
        cls.active_user = CommCareUser.create(
            domain='test',
            username='active',
            password='secret',
            is_active=True,
        )
        cls.active_user_2 = CommCareUser.create(
            domain='test',
            username='active2',
            password='secret',
            is_active=True,
        )
        cls.inactive_user = CommCareUser.create(
            domain='test',
            username='inactive',
            password='secret',
            is_active=False
        )
        cls.web_user = WebUser.create(
            domain='test',
            username='web',
            password='secret',
        )
        update_analytics_indexes()

    @classmethod
    def tearDownClass(cls):
        delete_all_users()
        cls.domain.delete()
        super(UserAnalyticsTest, cls).tearDownClass()

    def test_get_count_of_active_commcare_users_in_domain(self):
        self.assertEqual(2, get_count_of_active_commcare_users_in_domain('test'))

    def test_get_count_of_active_commcare_users_in_domain_no_results(self):
        self.assertEqual(0, get_count_of_active_commcare_users_in_domain('missing'))

    def test_get_count_of_inactive_commcare_users_in_domain(self):
        self.assertEqual(1, get_count_of_inactive_commcare_users_in_domain('test'))

    def test_get_count_of_inactive_commcare_users_in_domain_no_results(self):
        self.assertEqual(0, get_count_of_inactive_commcare_users_in_domain('missing'))

    def test_get_active_commcare_users_in_domain(self):
        users = get_active_commcare_users_in_domain('test')
        self.assertEqual(2, len(users))
        self.assertEqual(set(['active', 'active2']), set([u.username for u in users]))

    def test_get_inactive_commcare_users_in_domain(self):
        users = get_inactive_commcare_users_in_domain('test')
        self.assertEqual(1, len(users))
        self.assertEqual('inactive', users[0].username)

    def test_get_active_commcare_users_in_domain_no_results(self):
        self.assertEqual(0, len(get_active_commcare_users_in_domain('missing')))

    def test_get_inactive_commcare_users_in_domain_no_results(self):
        self.assertEqual(0, len(get_inactive_commcare_users_in_domain('missing')))
