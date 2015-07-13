from django.test import TestCase
from corehq.apps.users.models import WebUser, CommCareUser
from corehq.apps.users.dbaccessors.all_commcare_users import get_all_commcare_users_by_domain
from corehq.apps.domain.models import Domain


class AllCommCareUsersTest(TestCase):
    def setUp(self):
        self.ccdomain = Domain(name='cc_user_domain')
        self.ccdomain.save()
        self.other_domain = Domain(name='other_domain')
        self.other_domain.save()

        self.ccuser_1 = CommCareUser.create(
            domain=self.ccdomain.name,
            username='ccuser_1',
            password='secret',
            email='email@example.com',
        )
        self.ccuser_2 = CommCareUser.create(
            domain=self.ccdomain.name,
            username='ccuser_2',
            password='secret',
            email='email1@example.com',
        )
        self.web_user = WebUser.create(
            domain=self.ccdomain.name,
            username='webuser',
            password='secret',
            email='webuser@example.com',
        )
        self.ccuser_other_domain = CommCareUser.create(
            domain=self.other_domain.name,
            username='cc_user_other_domain',
            password='secret',
            email='email_other_domain@example.com',
        )

    def tearDown(self):
        self.ccdomain.delete()
        self.other_domain.delete()

    def test_get_all_commcare_users_by_domain(self):
        expected_users = [self.ccuser_2, self.ccuser_1]
        expected_usernames = [user.username for user in expected_users]
        actual_usernames = [user.username for user in get_all_commcare_users_by_domain(self.ccdomain.name)]
        self.assertItemsEqual(actual_usernames, expected_usernames)
