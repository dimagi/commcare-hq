from unittest import mock

from django.test import RequestFactory, SimpleTestCase

from corehq.apps.sso.utils.url_helpers import add_username_hint_to_login_url


class FakeIdp:

    def __init__(self, slug):
        self.slug = slug

    @classmethod
    def get_active_idp_by_username(cls, username):
        if username.endswith('foo.com'):
            return FakeIdp('loginhint')


@mock.patch(
    'corehq.apps.sso.utils.url_helpers.IdentityProvider.get_active_identity_provider_by_username',
    FakeIdp.get_active_idp_by_username
)
class TestAddUsernameHintToLoginUrl(SimpleTestCase):

    def setUp(self):
        super().setUp()
        self.request = RequestFactory().get('/sso/test')
        self.request.idp = FakeIdp('loginhint')
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
