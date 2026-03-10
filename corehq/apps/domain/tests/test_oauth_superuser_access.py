from django.test import RequestFactory, SimpleTestCase
from unittest.mock import patch, MagicMock

from corehq.apps.domain.decorators import _oauth2_check
from corehq.apps.users.models import WebUser
from corehq.util.global_request.api import set_request


def _make_superuser():
    user = WebUser()
    user.is_superuser = True
    return user


def _simulate_oauth_request():
    """Simulate a request that was authenticated via OAuth,
    returning the request object."""
    request = RequestFactory().get('/')
    mock_oauthlib_core = MagicMock()
    mock_request_info = MagicMock()
    mock_oauthlib_core.verify_request.return_value = (True, mock_request_info)

    with patch('corehq.apps.domain.decorators.get_oauthlib_core', return_value=mock_oauthlib_core):
        decorator = _oauth2_check(['access_apis'])
        wrapped = decorator(lambda req, *a, **kw: None)
        wrapped(request)

    return request


def _simulate_non_oauth_request():
    return RequestFactory().get('/')


class TestSuperuserIsGlobalAdminByAuthMethod(SimpleTestCase):
    """Superusers should be global admins for session-based requests,
    but NOT for OAuth-authenticated requests."""

    def setUp(self):
        self.addCleanup(set_request, None)

    def test_superuser_is_global_admin_for_non_oauth_request(self):
        set_request(_simulate_non_oauth_request())
        self.assertTrue(_make_superuser().is_global_admin())

    def test_superuser_is_not_global_admin_for_oauth_request(self):
        set_request(_simulate_oauth_request())
        self.assertFalse(_make_superuser().is_global_admin())

    def test_non_superuser_is_not_global_admin_for_non_oauth_request(self):
        set_request(_simulate_non_oauth_request())
        user = WebUser()
        user.is_superuser = False
        self.assertFalse(user.is_global_admin())

    def test_superuser_is_global_admin_when_no_request(self):
        set_request(None)
        self.assertTrue(_make_superuser().is_global_admin())
