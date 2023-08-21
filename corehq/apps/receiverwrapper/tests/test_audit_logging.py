from unittest.mock import patch, Mock, ANY

from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.receiverwrapper.views import post_api, secure_post
from corehq.apps.users.models import WebUser, HqPermissions
from corehq.apps.users.models_role import UserRole


def return_200(*args, **kwargs):
    return HttpResponse("success!", status=200)


def return_submission_run_resp(*args, **kwargs):
    submission_post_run = Mock()
    submission_post_run.response = return_200()
    return submission_post_run


@patch('corehq.apps.receiverwrapper.views.couchforms.get_instance_and_attachment', return_value=(Mock(), Mock()))
@patch('corehq.apps.receiverwrapper.views._record_metrics')
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

    def _create_user(self, edit_data=False, access_api=False):
        role = UserRole.create(
            self.domain, 'api-user', permissions=HqPermissions(
                edit_data=edit_data, access_api=access_api
            )
        )
        web_user = WebUser.create(self.domain, self.username, self.password,
                                  None, None, role_id=role.get_id)
        self.addCleanup(web_user.delete, None, None)
        return web_user

    def assert_api_response(self, status, url):
        self.client.login(username=self.username, password=self.password)
        self.assertEqual(self.client.post(url).status_code, status)

    def test_valid_request_not_logged(self, mock_record_metrics, mock_couchform_instance):
        url = reverse(post_api, args=[self.domain])
        self._create_user(edit_data=True, access_api=True)
        with patch('corehq.apps.receiverwrapper.views.notify_exception') as mock_notify_exception:
            self.assert_api_response(200, url)
            mock_notify_exception.assert_not_called()

    def test_invalid_request_logged(self, mock_record_metrics, mock_couchform_instance):
        url = reverse(secure_post, args=[self.domain])
        user = self._create_user(edit_data=True, access_api=True)
        with patch('corehq.apps.receiverwrapper.views.notify_exception') as mock_notify_exception:
            self.assert_api_response(200, url)
            mock_notify_exception.assert_called_once_with(ANY, message=ANY)
            args, kwargs = mock_notify_exception.call_args

            self.assertIsInstance(args[0], WSGIRequest)

            expected_message = (f'Restricted access by user samiam with id {user.get_id} and app_id None. '
                                f'Error details: Request not made from post_api handler for user')
            self.assertEqual(expected_message, kwargs.get("message"))
