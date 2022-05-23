from django.test import RequestFactory, TestCase

from corehq.apps.sso.models import AuthenticatedEmailDomain
from corehq.apps.sso.tests import generator
from corehq.apps.sso.utils.url_helpers import add_username_hint_to_login_url


class TestAddUsernameHintToLoginUrl(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account = generator.get_billing_account_for_idp()

        cls.idp = generator.create_idp('loginhint', cls.account)
        cls.idp.is_active = True
        cls.idp.save()
        AuthenticatedEmailDomain.objects.create(
            email_domain='foo.com',
            identity_provider=cls.idp,
        )

    def setUp(self):
        super().setUp()
        self.request = RequestFactory().get('/sso/test')
        self.request.idp = self.idp
        self.request.GET = {}

    def test_hint_is_added_to_login_url(self):
        self.request.GET['username'] = 'b@foo.com'
        full_url = add_username_hint_to_login_url('https://foo.com/oidc/login/user?biz=bar', self.request)
        self.assertEqual(full_url, 'https://foo.com/oidc/login/user?biz=bar&login_hint=b%40foo.com')

    def test_hint_is_not_added_to_url_due_to_idp_mismatch(self):
        self.request.GET['username'] = 'b@bar.com'
        full_url = add_username_hint_to_login_url('/login/user', self.request)
        self.assertEqual(full_url, '/login/user')

    def test_hint_is_not_added_to_url_due_to_missing_username(self):
        full_url = add_username_hint_to_login_url('/login/user', self.request)
        self.assertEqual(full_url, '/login/user')

    def test_hint_is_added_to_login_url_with_plus_in_email(self):
        self.request.GET['username'] = 'b+1@foo.com'
        full_url = add_username_hint_to_login_url('/login/user', self.request)
        self.assertEqual(full_url, '/login/user?login_hint=b%2B1%40foo.com')
