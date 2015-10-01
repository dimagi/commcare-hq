from django.test import TestCase
from corehq.apps.users.analytics import update_analytics_indexes, get_count_of_active_commcare_users_in_domain, \
    get_count_of_inactive_commcare_users_in_domain
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.users.models import CommCareUser


class UserAnalyticsTest(TestCase):

    @classmethod
    def setUpClass(cls):
        delete_all_users()
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
        update_analytics_indexes()

    def test_get_count_of_active_commcare_users_in_domain(self):
        self.assertEqual(2, get_count_of_active_commcare_users_in_domain('test'))

    def test_get_count_of_active_commcare_users_in_domain_no_results(self):
        self.assertEqual(0, get_count_of_active_commcare_users_in_domain('missing'))

    def test_get_count_of_inactive_commcare_users_in_domain(self):
        self.assertEqual(1, get_count_of_inactive_commcare_users_in_domain('test'))

    def test_get_count_of_inactive_commcare_users_in_domain_no_results(self):
        self.assertEqual(0, get_count_of_inactive_commcare_users_in_domain('missing'))
