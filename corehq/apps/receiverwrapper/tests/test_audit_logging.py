from unittest.mock import ANY, Mock, patch

from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.receiverwrapper.views import post_api, secure_post
from corehq.apps.users.models import CommCareUser, HqPermissions, WebUser
from corehq.apps.users.models_role import UserRole


def return_200(*args, **kwargs):
    return HttpResponse("success!", status=200)


def return_submission_run_resp(*args, **kwargs):
    submission_post_run = Mock()
    submission_post_run.response = return_200()
    return submission_post_run


@patch('corehq.apps.receiverwrapper.views.couchforms.get_instance_and_attachment',
       new=Mock(return_value=(Mock(), Mock())))
@patch('corehq.apps.receiverwrapper.views._record_metrics', new=Mock())
@patch('corehq.apps.receiverwrapper.views.SubmissionPost.run', new=return_submission_run_resp)
class TestAuditLoggingForFormSubmission(TestCase):
    domain = "submission-api-test"
    username = 'samiam'
    password = 'p@$$w0rd'

    @classmethod
    def setUpClass(cls):
        cls.domain_obj = create_domain(cls.domain)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()

    def _create_user(self, access_api, access_mobile_endpoints, user_cls=WebUser):
        role = UserRole.create(
            self.domain, 'api-user', permissions=HqPermissions(
                edit_data=access_api,
                access_api=access_api,
                access_mobile_endpoints=access_mobile_endpoints,
            )
        )
        user = user_cls.create(self.domain, self.username, self.password,
                               None, None, role_id=role.get_id)
        self.addCleanup(user.delete, None, None)
        return user

    def assert_api_response(self, status, url):
        self.client.login(username=self.username, password=self.password)
        self.assertEqual(self.client.post(url).status_code, status)

    def test_api_user_api_endpoint(self):
        url = reverse(post_api, args=[self.domain])
        self._create_user(access_api=True, access_mobile_endpoints=False)
        with patch('corehq.apps.receiverwrapper.views.notify_exception') as mock_notify_exception:
            self.assert_api_response(200, url)
            mock_notify_exception.assert_not_called()

    def test_web_user_regular_submission(self):
        url = reverse(secure_post, args=[self.domain])
        self._create_user(access_api=False, access_mobile_endpoints=True)
        with patch('corehq.apps.receiverwrapper.views.notify_exception') as mock_notify_exception:
            self.assert_api_response(200, url)
            mock_notify_exception.assert_not_called()

    def test_commcare_user_regular_submission(self):
        url = reverse(secure_post, args=[self.domain])
        self._create_user(access_api=False, access_mobile_endpoints=True, user_cls=CommCareUser)
        with patch('corehq.apps.receiverwrapper.views.notify_exception') as mock_notify_exception:
            self.assert_api_response(200, url)
            mock_notify_exception.assert_not_called()

    def test_api_user_regular_submission_gets_logged(self):
        url = reverse(secure_post, args=[self.domain])
        user = self._create_user(access_api=True, access_mobile_endpoints=False)
        with patch('corehq.apps.receiverwrapper.views.notify_exception') as mock_notify_exception:
            self.assert_api_response(200, url)
            mock_notify_exception.assert_called_once_with(ANY, message=ANY)
            args, kwargs = mock_notify_exception.call_args

            self.assertIsInstance(args[0], WSGIRequest)

            expected_message = f"NoMobileEndpointsAccess: invalid request by {user.get_id} on {self.domain}"
            self.assertEqual(expected_message, kwargs.get("message"))

    def test_web_user_no_api_access(self):
        url = reverse(post_api, args=[self.domain])
        self._create_user(access_api=False, access_mobile_endpoints=True)
        with patch('corehq.apps.receiverwrapper.views.notify_exception'):
            self.assert_api_response(403, url)
