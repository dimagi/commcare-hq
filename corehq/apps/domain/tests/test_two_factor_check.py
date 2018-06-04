from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase, RequestFactory
from corehq.util.test_utils import flag_enabled
from corehq.apps.users.models import CouchUser
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.domain.models import Domain
from corehq.apps.domain.decorators import _two_factor_required, two_factor_check
from mock import mock, Mock
import json


class TestTwoFactorCheck(TestCase):
    domain_name = 'test_domain'

    def setUp(self):

        self.domain = create_domain(self.domain_name)
        self.domain.two_factor_auth = False
        self.request = self.create_request(request_url='/account/')

    def tearDown(self):
        Domain.get_by_name(self.domain_name).delete()

    @classmethod
    def create_request(cls, request_url):
        request = RequestFactory().get(request_url)
        request.couch_user = CouchUser()
        return request

    def test_two_factor_required_for_superuser(self):
        view_func = 'dummy_view_func'
        request = self.request
        self.assertFalse(_two_factor_required(view_func, self.domain, request.couch_user))

        request.couch_user.is_superuser = True
        self.assertTrue(_two_factor_required(view_func, self.domain, request.couch_user))

    def test_two_factor_check_superuser(self):
        self.request.couch_user.is_superuser = True
        response = self._test_two_factor_check(self.request, expect_called=False)
        data = json.loads(response.content)
        self.assertDictEqual(data, {'error': 'must send X-CommcareHQ-OTP header'})

    def test_two_factor_check_non_superuser(self):
        response = self._test_two_factor_check(self.request, expect_called=True)
        self.assertEqual(response, 'Function was called!')

    def _test_two_factor_check(self, request, expect_called):
        mock_fn_to_call = Mock(return_value="Function was called!")
        mock_fn_to_call.__name__ = b'test_name'
        api_key = None
        view_func = 'dummy_view_func'
        two_factor_check_fn = two_factor_check(view_func, api_key)
        function_getting_checked_with_auth = two_factor_check_fn(mock_fn_to_call)
        with mock.patch('corehq.apps.domain.decorators._ensure_request_couch_user',
                        return_value=request.couch_user):
            response = function_getting_checked_with_auth(request, self.domain.name)
            if expect_called:
                mock_fn_to_call.assert_called_once()
            else:
                mock_fn_to_call.assert_not_called()
            return response
