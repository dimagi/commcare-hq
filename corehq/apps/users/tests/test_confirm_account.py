from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.account_confirmation import should_send_account_confirmation
from corehq.apps.users.exceptions import IllegalAccountConfirmation
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.util.test_utils import generate_cases


class TestAccountConfirmation(TestCase):
    domain = 'test_account_confirmation'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = create_domain(cls.domain)

    def setUp(self):
        self.username = 'mw1'
        self.password = 's3cr3t'
        self.user = CommCareUser.create(
            self.domain,
            self.username,
            self.password,
            None,
            None,
            email='mw1@example.com',
            is_account_confirmed=False,
        )
        # confirm user can't login
        self.assertEqual(False, self.client.login(username=self.username, password=self.password))

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()
        from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
        delete_all_users()
        super().tearDownClass()

    def tearDown(self):
        self.user.delete()

    def test_confirm_account(self):

        # confirm user can't login
        self.assertEqual(False, self.client.login(username=self.username, password=self.password))

        new_password = 'm0r3s3cr3t!'
        self.user.confirm_account(password=new_password)

        # confirm user can't login with old password
        self.assertEqual(False, self.client.login(username=self.username, password=self.password))
        # but can with new password
        self.assertEqual(True, self.client.login(username=self.username, password=new_password))

    def test_cant_confirm_twice(self):
        self.user.confirm_account('abc')
        with self.assertRaises(IllegalAccountConfirmation):
            self.user.confirm_account('def')


@generate_cases([
    (CommCareUser(username='normal', is_account_confirmed=False), True),
    (CommCareUser(username='already_confirmed', is_account_confirmed=True), False),
    (WebUser(is_account_confirmed=False), False),
])
def test_should_send_account_confirmation(self, user, result):
    self.assertEqual(result, should_send_account_confirmation(user))
