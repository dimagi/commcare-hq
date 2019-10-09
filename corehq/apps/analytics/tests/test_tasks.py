from unittest.case import TestCase
from unittest.mock import Mock, patch

from email_validator import EmailNotValidError
from requests import HTTPError

from corehq.apps.analytics.tasks import _raise_for_urllib3_response, _track_on_hubspot, _track_on_hubspot_by_email, \
    set_analytics_opt_out, batch_track_on_hubspot, _hubspot_post, _get_user_hubspot_id, _get_client_ip, \
    _send_form_to_hubspot, track_web_user_registration_hubspot, send_hubspot_form, track_workflow, _email_is_valid, \
    _track_periodic_data_on_kiss, _log_response, get_subscription_properties_by_user, \
    _send_post_data, _send_hubspot_form_request, update_hubspot_properties, track_user_sign_in_on_hubspot, \
    HUBSPOT_SIGNIN_FORM_ID, track_built_app_on_hubspot, track_confirmed_account_on_hubspot, send_hubspot_form_task, \
    track_clicked_deploy_on_hubspot, HUBSPOT_CLICKED_DEPLOY_FORM_ID, track_job_candidate_on_hubspot, \
    track_clicked_signup_on_hubspot, HUBSPOT_CLICKED_SIGNUP_FORM, _track_workflow_task, identify, _get_export_count, \
    update_subscription_properties_by_domain, update_subscription_properties_by_user, track_periodic_data


class TestTasks(TestCase):

    def test__raise_for_urllib3_response_not_raises_error(self):
        mock_response = Mock(status=123)

        response = _raise_for_urllib3_response(mock_response)

        self.assertEqual(response, None)

    def test__raise_for_urllibb3_response_raises_error(self):
        mock_response = Mock(status=420)

        with self.assertRaises(HTTPError):
            _raise_for_urllib3_response(mock_response)

    @patch('corehq.apps.analytics.tasks._hubspot_post')
    @patch('corehq.apps.analytics.tasks.six.moves.urllib.parse.quote')
    @patch('corehq.apps.analytics.tasks.json')
    def test___track_on_hubspot_analytics_enabled_true(self, mock_json, mock_quote, mock__hubspot_post):
        mock_webuser = Mock(analytics_enabled=True)
        mock_properties = {
            'key': 'value'
        }

        _track_on_hubspot(mock_webuser, mock_properties)

        self.assertEqual(mock__hubspot_post.call_count, 1)
        self.assertEqual(mock_quote.call_count, 1)
        self.assertEqual(mock_webuser.get_email.call_count, 1)
        self.assertEqual(mock_json.dumps.call_count, 1)

    @patch('corehq.apps.analytics.tasks._hubspot_post')
    @patch('corehq.apps.analytics.tasks.six.moves.urllib.parse.quote')
    @patch('corehq.apps.analytics.tasks.json')
    def test___track_on_hubspot_analytics_enabled_false(self, mock_json, mock_quote, mock__hubspot_post):
        mock_webuser = Mock(analytics_enabled=False)
        mock_properties = {
            'key': 'value'
        }

        _track_on_hubspot(mock_webuser, mock_properties)

        self.assertEqual(mock__hubspot_post.call_count, 0)
        self.assertEqual(mock_quote.call_count, 0)
        self.assertEqual(mock_webuser.get_email.call_count, 0)
        self.assertEqual(mock_json.dumps.call_count, 0)

    @patch('corehq.apps.analytics.tasks._hubspot_post')
    @patch('corehq.apps.analytics.tasks.six.moves.urllib.parse.quote')
    @patch('corehq.apps.analytics.tasks.json')
    def test__track_on_hubspot_by_email(self, mock_json, mock_quote, mock__hubspot_post):
        _track_on_hubspot_by_email('email', {'key': 'value'})

        self.assertEqual(mock__hubspot_post.call_count, 1)
        self.assertEqual(mock_quote.call_count, 1)
        self.assertEqual(mock_json.dumps.call_count, 1)

    @patch('corehq.apps.analytics.tasks._hubspot_post')
    @patch('corehq.apps.analytics.tasks.six.moves.urllib.parse.quote')
    @patch('corehq.apps.analytics.tasks.json')
    def test_set_analytics_opt_out(self, mock_json, mock_quote, mock__hubspot_post):
        mock_webuser = Mock(analytics_enabled=True)
        mock_properties = {
            'key': 'value'
        }

        set_analytics_opt_out(mock_webuser, mock_properties)

        self.assertEqual(mock__hubspot_post.call_count, 1)
        self.assertEqual(mock_quote.call_count, 1)
        self.assertEqual(mock_webuser.get_email.call_count, 1)
        self.assertEqual(mock_json.dumps.call_count, 1)

    @patch('corehq.apps.analytics.tasks._hubspot_post')
    def test_batch_track_on_hubspot(self, mock__hubspot_post):
        mock_json = 'I\'m Json'

        batch_track_on_hubspot(mock_json)

        self.assertEqual(mock__hubspot_post.call_count, 1)

    @patch('corehq.apps.analytics.tasks.settings')
    @patch('corehq.apps.analytics.tasks._send_post_data')
    @patch('corehq.apps.analytics.tasks._log_response')
    def test___hubspot_post_api_key_not_none(self, mock__log_response, mock__send_post_data, mock_settings):
        mock_response = Mock()
        mock_settings.ANALYTICS_IDS.get.return_value = 'Definitely not None'
        mock__send_post_data.return_value = mock_response

        _hubspot_post('url', 'data')

        self.assertEqual(mock__send_post_data.call_count, 1)
        self.assertEqual(mock__log_response.call_count, 1)
        self.assertEqual(mock_response.raise_for_status.call_count, 1)

    @patch('corehq.apps.analytics.tasks.settings')
    @patch('corehq.apps.analytics.tasks._send_post_data')
    @patch('corehq.apps.analytics.tasks._log_response')
    def test___hubspot_post_api_key_equals_none(self, mock__log_response, mock__send_post_data, mock_settings):
        mock_response = Mock()
        mock_settings.ANALYTICS_IDS.get.return_value = None
        mock__send_post_data.return_value = mock_response

        _hubspot_post('url', 'data')

        self.assertEqual(mock__send_post_data.call_count, 0)
        self.assertEqual(mock__log_response.call_count, 0)
        self.assertEqual(mock_response.raise_for_status.call_count, 0)

    @patch('corehq.apps.analytics.tasks.requests')
    def test__send_post_data(self, mock_requests):
        _send_post_data('url', 'params', 'data', 'headers')

        self.assertEqual(mock_requests.post.call_count, 1)
        mock_requests.post.assert_called_with('url', data='data', headers='headers', params='params')

    @patch('corehq.apps.analytics.tasks.settings')
    @patch('corehq.apps.analytics.tasks.requests')
    @patch('corehq.apps.analytics.tasks.six.moves.urllib.parse.quote')
    def test__get_user_hubspot_id_api_key_not_none_status_code_not_404(self, mock_quote, mock_requests, mock_settings):
        mock_webuser = Mock(analytics_enabled=True)
        mock_req = Mock(status_code=200)
        mock_req.json.return_value.get.return_value = 'I\'m value'
        mock_settings.ANALYTICS_IDS.get.return_value = 'Definitely not None'
        mock_requests.get.return_value = mock_req

        response = _get_user_hubspot_id(mock_webuser)

        self.assertEqual(mock_requests.get.call_count, 1)
        self.assertEqual(mock_quote.call_count, 1)
        self.assertEqual(mock_req.raise_for_status.call_count, 1)
        self.assertEqual(mock_req.json.call_count, 1)
        self.assertEqual(mock_req.json.return_value.get.call_count, 1)
        self.assertEqual(response, 'I\'m value')

    @patch('corehq.apps.analytics.tasks.settings')
    @patch('corehq.apps.analytics.tasks.requests')
    @patch('corehq.apps.analytics.tasks.six.moves.urllib.parse.quote')
    def test__get_user_hubspot_id_api_key_not_none_status_code_is_404(self, mock_quote, mock_requests, mock_settings):
        mock_webuser = Mock(analytics_enabled=True)
        mock_req = Mock(status_code=404)
        mock_settings.ANALYTICS_IDS.get.return_value = 'Definitely not None'
        mock_requests.get.return_value = mock_req

        response = _get_user_hubspot_id(mock_webuser)

        self.assertEqual(mock_requests.get.call_count, 1)
        self.assertEqual(mock_quote.call_count, 1)
        self.assertEqual(mock_req.raise_for_status.call_count, 0)
        self.assertEqual(mock_req.json.call_count, 0)
        self.assertEqual(mock_req.json.return_value.get.call_count, 0)
        self.assertEqual(response, None)

    @patch('corehq.apps.analytics.tasks.settings')
    @patch('corehq.apps.analytics.tasks.requests')
    @patch('corehq.apps.analytics.tasks.six.moves.urllib.parse.quote')
    def test__get_user_hubspot_id_api_key_equals_none(self, mock_quote, mock_requests, mock_settings):
        mock_webuser = Mock(analytics_enabled=True)
        mock_req = Mock(status_code=200)
        mock_settings.ANALYTICS_IDS.get.return_value = None
        mock_requests.get.return_value = mock_req

        response = _get_user_hubspot_id(mock_webuser)

        self.assertEqual(mock_requests.get.call_count, 0)
        self.assertEqual(mock_quote.call_count, 0)
        self.assertEqual(mock_req.raise_for_status.call_count, 0)
        self.assertEqual(mock_req.json.call_count, 0)
        self.assertEqual(mock_req.json.return_value.get.call_count, 0)
        self.assertEqual(response, None)

    def test__get_client_ip_x_forwarded_for_not_none(self):
        mock_meta = Mock()
        mock_meta.get.return_value = 'Definitely not None, or is it?'

        response = _get_client_ip(mock_meta)

        self.assertEqual(response, 'Definitely not None')

    def test__get_client_ip_x_forwarded_equals_none(self):
        mock_meta = Mock()
        mock_meta.get.side_effect = [None, 'not None']

        response = _get_client_ip(mock_meta)

        self.assertEqual(response, 'not None')

    @patch('corehq.apps.analytics.tasks.json')
    @patch('corehq.apps.analytics.tasks._get_client_ip')
    @patch('corehq.apps.analytics.tasks._send_hubspot_form_request')
    @patch('corehq.apps.analytics.tasks._log_response')
    def test__send_form_to_hubspot_webuser_analytics_enabled_false(self, mock__log_response,
                                                                   mock__send_hubspot_form_request, mock__get_client_ip,
                                                                   mock_json):
        mock_webuser = Mock(analytics_enabled=False)
        mock_response = Mock()
        mock__send_hubspot_form_request.return_value = mock_response

        response = _send_form_to_hubspot('form_id', mock_webuser, 'cookie', 'meta')

        self.assertEqual(mock_json.dumps.call_count, 0)
        self.assertEqual(mock__get_client_ip.call_count, 0)
        self.assertEqual(mock__send_hubspot_form_request.call_count, 0)
        self.assertEqual(mock__log_response.call_count, 0)
        self.assertEqual(mock_response.raise_for_status.call_count, 0)
        self.assertEqual(response, None)

    @patch('corehq.apps.analytics.tasks.analytics_enabled_for_email')
    @patch('corehq.apps.analytics.tasks.json')
    @patch('corehq.apps.analytics.tasks._get_client_ip')
    @patch('corehq.apps.analytics.tasks._send_hubspot_form_request')
    @patch('corehq.apps.analytics.tasks._log_response')
    def test__send_form_to_hubspot_webuser_analytics_enabled_for_email_false(self, mock__log_response,
                                                                             mock__send_hubspot_form_request,
                                                                             mock__get_client_ip, mock_json,
                                                                             mock_analytics_enabled_for_email):
        mock_webuser = False
        mock_analytics_enabled_for_email.return_value = False
        mock_response = Mock()
        mock__send_hubspot_form_request.return_value = mock_response

        response = _send_form_to_hubspot('form_id', mock_webuser, 'cookie', 'meta')

        self.assertEqual(mock_json.dumps.call_count, 0)
        self.assertEqual(mock__get_client_ip.call_count, 0)
        self.assertEqual(mock__send_hubspot_form_request.call_count, 0)
        self.assertEqual(mock__log_response.call_count, 0)
        self.assertEqual(mock_response.raise_for_status.call_count, 0)
        self.assertEqual(response, None)

    @patch('corehq.apps.analytics.tasks.settings')
    @patch('corehq.apps.analytics.tasks.json')
    @patch('corehq.apps.analytics.tasks._get_client_ip')
    @patch('corehq.apps.analytics.tasks._send_hubspot_form_request')
    @patch('corehq.apps.analytics.tasks._log_response')
    def test__send_form_to_hubspot_with_hubspot_id_and_cookie(self, mock__log_response,
                                                              mock__send_hubspot_form_request,
                                                              mock__get_client_ip,
                                                              mock_json, mock_settings):
        mock_webuser = Mock(analytics_enabled=True)
        mock_settings.ANALYTICS_IDS.get.return_value = 'id_1'
        mock_response = Mock()
        mock__send_hubspot_form_request.return_value = mock_response

        response = _send_form_to_hubspot('form_id', mock_webuser, 'cookie', 'meta')

        self.assertEqual(mock_json.dumps.call_count, 1)
        self.assertEqual(mock__get_client_ip.call_count, 1)
        self.assertEqual(mock__send_hubspot_form_request.call_count, 1)
        self.assertEqual(mock__log_response.call_count, 1)
        self.assertEqual(mock_response.raise_for_status.call_count, 1)
        self.assertEqual(response, None)

    @patch('corehq.apps.analytics.tasks.requests')
    def test__send_hubspot_form_request(self, mock_requests):
        _send_hubspot_form_request('id_1', 'id_2', 'data')

        self.assertEqual(mock_requests.post.call_count, 1)
        mock_requests.post.assert_called_with('https://forms.hubspot.com/uploads/form/v2/id_1/id_2', data='data')

    @patch('corehq.apps.analytics.tasks._get_user_hubspot_id')
    @patch('corehq.apps.analytics.tasks._track_on_hubspot')
    def test_update_hubspot_properties_no_vid(self, mock__track_on_hubspot, mock__get_user_hubspot_id):
        mock_webuser = Mock()
        mock__get_user_hubspot_id.return_value = None

        update_hubspot_properties(mock_webuser, 'properties')

        self.assertEqual(mock__get_user_hubspot_id.call_count, 1)
        mock__get_user_hubspot_id.assert_called_with(mock_webuser)
        self.assertEqual(mock__track_on_hubspot.call_count, 0)

    @patch('corehq.apps.analytics.tasks._get_user_hubspot_id')
    @patch('corehq.apps.analytics.tasks._track_on_hubspot')
    def test_update_hubspot_properties_with_vid(self, mock__track_on_hubspot, mock__get_user_hubspot_id):
        mock_webuser = Mock()
        mock__get_user_hubspot_id.return_value = True

        update_hubspot_properties(mock_webuser, 'properties')

        self.assertEqual(mock__get_user_hubspot_id.call_count, 1)
        mock__get_user_hubspot_id.assert_called_with(mock_webuser)
        self.assertEqual(mock__track_on_hubspot.call_count, 1)
        mock__track_on_hubspot.assert_called_with(mock_webuser, 'properties')

    @patch('corehq.apps.analytics.tasks.settings')
    @patch('corehq.apps.analytics.tasks.get_instance_string')
    @patch('corehq.apps.analytics.tasks.get_ab_test_properties')
    @patch('corehq.apps.analytics.tasks.send_hubspot_form')
    def test_track_web_user_registration_hubspot_no_hubspot_api_id(self, mock_send_hubspot_form,
                                                                   mock_get_ab_test_properties,
                                                                   mock_get_instance_string, mock_settings):
        mock_webuser = Mock()
        mock_settings.ANALYTICS_IDS.get.return_value = False

        resposne = track_web_user_registration_hubspot('request', mock_webuser, 'properties')

        self.assertEqual(mock_get_instance_string.call_count, 0)
        self.assertEqual(mock_webuser.date_joined.isoformat.call_count, 0)
        self.assertEqual(mock_get_ab_test_properties.call_count, 0)
        self.assertEqual(mock_send_hubspot_form.call_count, 0)
        self.assertEqual(resposne, None)

    @patch('corehq.apps.analytics.tasks.settings')
    @patch('corehq.apps.analytics.tasks.get_instance_string')
    @patch('corehq.apps.analytics.tasks.get_ab_test_properties')
    @patch('corehq.apps.analytics.tasks.send_hubspot_form')
    def test_track_web_user_registration_hubspot_no_hubspot_api_id(self, mock_send_hubspot_form,
                                                                   mock_get_ab_test_properties,
                                                                   mock_get_instance_string, mock_settings):
        mock_webuser = Mock(phone_numbers=['phone_1', 'phone_2'])
        mock_settings.ANALYTICS_IDS.get.return_value = 'id_1'

        resposne = track_web_user_registration_hubspot('request', mock_webuser, ['te', 'st'])

        self.assertEqual(mock_get_instance_string.call_count, 1)
        self.assertEqual(mock_webuser.date_joined.isoformat.call_count, 1)
        self.assertEqual(mock_get_ab_test_properties.call_count, 1)
        self.assertEqual(mock_send_hubspot_form.call_count, 1)
        self.assertEqual(resposne, None)

    @patch('corehq.apps.analytics.tasks._send_form_to_hubspot')
    def test_track_user_sign_in_on_hubspot(self, mock__send_form_to_hubspot):
        track_user_sign_in_on_hubspot('webuser', 'hubspot_cookie', 'meta', 'path')

        self.assertEqual(mock__send_form_to_hubspot.call_count, 1)
        mock__send_form_to_hubspot.assert_called_with(HUBSPOT_SIGNIN_FORM_ID, 'webuser', 'hubspot_cookie', 'meta')

    @patch('corehq.apps.analytics.tasks._get_user_hubspot_id')
    @patch('corehq.apps.analytics.tasks._track_on_hubspot')
    def test_track_built_app_on_hubspot_no_vid(self, mock__track_on_hubspot, mock__get_user_hubspot_id):
        mock_websuer = Mock()
        mock__get_user_hubspot_id.return_value = None

        track_built_app_on_hubspot(mock_websuer)

        self.assertEqual(mock__get_user_hubspot_id.call_count, 1)
        mock__get_user_hubspot_id.assert_called_with(mock_websuer)
        self.assertEqual(mock__track_on_hubspot.call_count, 0)

    @patch('corehq.apps.analytics.tasks._get_user_hubspot_id')
    @patch('corehq.apps.analytics.tasks._track_on_hubspot')
    def test_track_built_app_on_hubspot_with_vid(self, mock__track_on_hubspot, mock__get_user_hubspot_id):
        mock_webuser = Mock()
        mock__get_user_hubspot_id.return_value = True

        track_built_app_on_hubspot(mock_webuser)

        self.assertEqual(mock__get_user_hubspot_id.call_count, 1)
        mock__get_user_hubspot_id.assert_called_with(mock_webuser)
        self.assertEqual(mock__track_on_hubspot.call_count, 1)
        mock__track_on_hubspot.assert_called_with(mock_webuser, {'built_app': True})

    @patch('corehq.apps.analytics.tasks._get_user_hubspot_id')
    @patch('corehq.apps.analytics.tasks._track_on_hubspot')
    def test_track_confirmed_account_on_hubspot_no_vid(self, mock__track_on_hubspot, mock__get_user_hubspot_id):
        mock_webuser = Mock()
        mock__get_user_hubspot_id.return_value = None

        track_confirmed_account_on_hubspot(mock_webuser)

        self.assertEqual(mock__get_user_hubspot_id.call_count, 1)
        mock__get_user_hubspot_id.assert_called_with(mock_webuser)
        self.assertEqual(mock__track_on_hubspot.call_count, 0)

    @patch('corehq.apps.analytics.tasks._get_user_hubspot_id')
    @patch('corehq.apps.analytics.tasks._track_on_hubspot')
    def test_track_confirmed_account_on_hubspot_with_vid(self, mock__track_on_hubspot, mock__get_user_hubspot_id):
        mock_webuser = Mock(domain_memberships=[Mock(domain='domain')])
        mock__get_user_hubspot_id.return_value = True

        track_confirmed_account_on_hubspot(mock_webuser)

        self.assertEqual(mock__get_user_hubspot_id.call_count, 1)
        mock__get_user_hubspot_id.assert_called_with(mock_webuser)
        self.assertEqual(mock__track_on_hubspot.call_count, 1)
        mock__track_on_hubspot.assert_called_with(mock_webuser, {
            'confirmed_account': True,
            'domain': 'domain'
        })

    @patch('corehq.apps.analytics.tasks._get_user_hubspot_id')
    @patch('corehq.apps.analytics.tasks._track_on_hubspot')
    def test_track_confirmed_account_on_hubspot_error(self, mock__track_on_hubspot, mock__get_user_hubspot_id):
        mock_webuser = Mock(domain_memberships=[])
        mock__get_user_hubspot_id.return_value = True

        track_confirmed_account_on_hubspot(mock_webuser)

        self.assertEqual(mock__get_user_hubspot_id.call_count, 1)
        mock__get_user_hubspot_id.assert_called_with(mock_webuser)
        self.assertEqual(mock__track_on_hubspot.call_count, 1)
        mock__track_on_hubspot.assert_called_with(mock_webuser, {
            'confirmed_account': True,
            'domain': ''
        })

    @patch('corehq.apps.analytics.tasks.get_meta')
    @patch('corehq.apps.analytics.tasks.send_hubspot_form_task')
    def test_send_hubspot_form_arguments_insufficient(self, mock_send_hubspot_form_task, mock_get_meta):
        mock_request = Mock()
        mock_user = Mock()
        mock_user.is_web_user.return_value = False

        with patch('corehq.apps.analytics.tasks.getattr') as mock_getattr:
            send_hubspot_form('id_1', mock_request, mock_user)

            self.assertEqual(mock_getattr.call_count, 0)

        self.assertEqual(mock_user.is_web_user.call_count, 1)
        self.assertEqual(mock_get_meta.call_count, 0)
        self.assertEqual(mock_request.COOKIES.get.call_count, 0)
        self.assertEqual(mock_send_hubspot_form_task.delay.call_count, 0)

    @patch('corehq.apps.analytics.tasks.get_meta')
    @patch('corehq.apps.analytics.tasks.send_hubspot_form_task')
    def test_send_hubspot_form_arguments_insufficient_no_user(self, mock_send_hubspot_form_task, mock_get_meta):
        mock_request = Mock()
        mock_user = Mock()
        mock_user.is_web_user.return_value = False

        with patch('corehq.apps.analytics.tasks.getattr', return_value=mock_user) as mock_getattr:
            send_hubspot_form('id_1', mock_request, None)

            self.assertEqual(mock_getattr.call_count, 1)

        self.assertEqual(mock_user.is_web_user.call_count, 1)
        self.assertEqual(mock_get_meta.call_count, 0)
        self.assertEqual(mock_request.COOKIES.get.call_count, 0)
        self.assertEqual(mock_send_hubspot_form_task.delay.call_count, 0)

    @patch('corehq.apps.analytics.tasks.get_meta')
    @patch('corehq.apps.analytics.tasks.send_hubspot_form_task')
    def test_send_hubspot_form_arguments_sufficient(self, mock_send_hubspot_form_task, mock_get_meta):
        mock_request = Mock()
        mock_user = Mock()
        mock_user.is_web_user.return_value = True

        with patch('corehq.apps.analytics.tasks.getattr') as mock_getattr:
            send_hubspot_form('id_1', mock_request, mock_user)

            self.assertEqual(mock_getattr.call_count, 0)

        self.assertEqual(mock_user.is_web_user.call_count, 1)
        self.assertEqual(mock_get_meta.call_count, 1)
        self.assertEqual(mock_request.COOKIES.get.call_count, 1)
        self.assertEqual(mock_send_hubspot_form_task.delay.call_count, 1)

    @patch('corehq.apps.analytics.tasks.get_meta')
    @patch('corehq.apps.analytics.tasks.send_hubspot_form_task')
    def test_send_hubspot_form_arguments_sufficient_no_user(self, mock_send_hubspot_form_task, mock_get_meta):
        mock_request = Mock()
        mock_user = Mock()
        mock_user.is_web_user.return_value = True

        with patch('corehq.apps.analytics.tasks.getattr', return_value=mock_user) as mock_getattr:
            send_hubspot_form('id_1', mock_request, None)

            self.assertEqual(mock_getattr.call_count, 1)

        self.assertEqual(mock_user.is_web_user.call_count, 1)
        self.assertEqual(mock_get_meta.call_count, 1)
        self.assertEqual(mock_request.COOKIES.get.call_count, 1)
        self.assertEqual(mock_send_hubspot_form_task.delay.call_count, 1)

    @patch('corehq.apps.analytics.tasks.WebUser')
    @patch('corehq.apps.analytics.tasks._send_form_to_hubspot')
    def test_send_hubspot_form_task(self, mock__send_form_to_hubspot, mock_WebUser):
        mock_webuser = Mock()
        mock_WebUser.get_by_user_id.return_value = mock_webuser

        send_hubspot_form_task('form_id', 'webuser_id', 'cookie', 'meta')

        self.assertEqual(mock_WebUser.get_by_user_id.call_count, 1)
        mock_WebUser.get_by_user_id.assert_called_with('webuser_id')
        self.assertEqual(mock__send_form_to_hubspot.call_count, 1)
        mock__send_form_to_hubspot.assert_called_with('form_id', mock_webuser, 'cookie', 'meta', extra_fields=None)

    @patch('corehq.apps.analytics.tasks.deterministic_random')
    @patch('corehq.apps.analytics.tasks._send_form_to_hubspot')
    def test_track_clicked_deploy_on_hubspot_with_A(self, mock__send_form_to_hubspot, mock_deterministic_random):
        mock_webuser = Mock(username='Doge')
        mock_deterministic_random.return_value = 1
        mock_ab = {
            'a_b_variable_deploy': 'A',
        }

        track_clicked_deploy_on_hubspot(mock_webuser, 'cookie', 'meta')

        self.assertEqual(mock_deterministic_random.call_count, 1)
        mock_deterministic_random.assert_called_with(mock_webuser.username + 'a_b_variable_deploy')
        self.assertEqual(mock__send_form_to_hubspot.call_count, 1)
        mock__send_form_to_hubspot.assert_called_with(HUBSPOT_CLICKED_DEPLOY_FORM_ID, mock_webuser,
                                                      'cookie', 'meta', extra_fields=mock_ab)

    @patch('corehq.apps.analytics.tasks.deterministic_random')
    @patch('corehq.apps.analytics.tasks._send_form_to_hubspot')
    def test_track_clicked_deploy_on_hubspot_with_B(self, mock__send_form_to_hubspot, mock_deterministic_random):
        mock_webuser = Mock(username='Doge')
        mock_deterministic_random.return_value = 0.2
        mock_ab = {
            'a_b_variable_deploy': 'B',
        }

        track_clicked_deploy_on_hubspot(mock_webuser, 'cookie', 'meta')

        self.assertEqual(mock_deterministic_random.call_count, 1)
        mock_deterministic_random.assert_called_with(mock_webuser.username + 'a_b_variable_deploy')
        self.assertEqual(mock__send_form_to_hubspot.call_count, 1)
        mock__send_form_to_hubspot.assert_called_with(HUBSPOT_CLICKED_DEPLOY_FORM_ID, mock_webuser,
                                                      'cookie', 'meta', extra_fields=mock_ab)

    @patch('corehq.apps.analytics.tasks._track_on_hubspot_by_email')
    def test_track_job_candidate_on_hubspot(self, mock__track_on_hubspot_by_email):
        track_job_candidate_on_hubspot('email')

        self.assertEqual(mock__track_on_hubspot_by_email.call_count, 1)
        mock__track_on_hubspot_by_email.assert_called_with('email', properties={'job_candidate': True})

    @patch('corehq.apps.analytics.tasks.deterministic_random')
    @patch('corehq.apps.analytics.tasks._send_form_to_hubspot')
    def test_track_clicked_signup_on_hubspot_without_email(self, mock__send_form_to_hubspot,
                                                           mock_deterministick_random):
        mock_email = ''
        mock_deterministick_random.return_value = 0

        track_clicked_signup_on_hubspot(mock_email, 'cookie', 'meta')

        self.assertEqual(mock_deterministick_random.call_count, 1)
        mock_deterministick_random.assert_called_with(mock_email + 'a_b_test_variable_newsletter')
        self.assertEqual(mock__send_form_to_hubspot.call_count, 0)

    @patch('corehq.apps.analytics.tasks.deterministic_random')
    @patch('corehq.apps.analytics.tasks._send_form_to_hubspot')
    def test_track_clicked_signup_on_hubspot_with_email_number_less_than_033(self, mock__send_form_to_hubspot,
                                                                             mock_deterministick_random):
        mock_email = 'email'
        mock_data = {
            'lifecyclestage': 'subscriber',
            'a_b_test_variable_newsletter': 'A',
        }
        mock_deterministick_random.return_value = 0.2

        track_clicked_signup_on_hubspot(mock_email, 'cookie', 'meta')

        self.assertEqual(mock_deterministick_random.call_count, 1)
        mock_deterministick_random.assert_called_with(mock_email + 'a_b_test_variable_newsletter')
        self.assertEqual(mock__send_form_to_hubspot.call_count, 1)
        mock__send_form_to_hubspot.assert_called_with(
            HUBSPOT_CLICKED_SIGNUP_FORM, None, 'cookie', 'meta',
            extra_fields=mock_data, email=mock_email
        )

    @patch('corehq.apps.analytics.tasks.deterministic_random')
    @patch('corehq.apps.analytics.tasks._send_form_to_hubspot')
    def test_track_clicked_signup_on_hubspot_with_email_number_less_than_067(self, mock__send_form_to_hubspot,
                                                                             mock_deterministick_random):
        mock_email = 'email'
        mock_data = {
            'lifecyclestage': 'subscriber',
            'a_b_test_variable_newsletter': 'B',
        }
        mock_deterministick_random.return_value = 0.5

        track_clicked_signup_on_hubspot(mock_email, 'cookie', 'meta')

        self.assertEqual(mock_deterministick_random.call_count, 1)
        mock_deterministick_random.assert_called_with(mock_email + 'a_b_test_variable_newsletter')
        self.assertEqual(mock__send_form_to_hubspot.call_count, 1)
        mock__send_form_to_hubspot.assert_called_with(
            HUBSPOT_CLICKED_SIGNUP_FORM, None, 'cookie', 'meta',
            extra_fields=mock_data, email=mock_email
        )

    @patch('corehq.apps.analytics.tasks.deterministic_random')
    @patch('corehq.apps.analytics.tasks._send_form_to_hubspot')
    def test_track_clicked_signup_on_hubspot_with_email_number_more_than_067(self, mock__send_form_to_hubspot,
                                                                             mock_deterministick_random):
        mock_email = 'email'
        mock_data = {
            'lifecyclestage': 'subscriber',
            'a_b_test_variable_newsletter': 'C',
        }
        mock_deterministick_random.return_value = 1

        track_clicked_signup_on_hubspot(mock_email, 'cookie', 'meta')

        self.assertEqual(mock_deterministick_random.call_count, 1)
        mock_deterministick_random.assert_called_with(mock_email + 'a_b_test_variable_newsletter')
        self.assertEqual(mock__send_form_to_hubspot.call_count, 1)
        mock__send_form_to_hubspot.assert_called_with(
            HUBSPOT_CLICKED_SIGNUP_FORM, None, 'cookie', 'meta',
            extra_fields=mock_data, email=mock_email
        )

    @patch('corehq.apps.analytics.tasks.analytics_enabled_for_email')
    @patch('corehq.apps.analytics.tasks.unix_time')
    @patch('corehq.apps.analytics.tasks.datetime')
    @patch('corehq.apps.analytics.tasks._track_workflow_task')
    @patch('corehq.apps.analytics.tasks.notify_exception')
    def test_track_workflow_arguments_insufficient(self, mock_notify_exception, mock__track_workflow_task,
                                                   mock_datetime, mock_unix_time, mock_analytics_enabled_for_email):
        mock_analytics_enabled_for_email.return_value = False

        track_workflow('email', 'event')

        self.assertEqual(mock_analytics_enabled_for_email.call_count, 1)
        self.assertEqual(mock_unix_time.call_count, 0)
        self.assertEqual(mock_datetime.utcnow.call_count, 0)
        self.assertEqual(mock__track_workflow_task.delay.call_count, 0)
        self.assertEqual(mock_notify_exception.call_count, 0)

    @patch('corehq.apps.analytics.tasks.analytics_enabled_for_email')
    @patch('corehq.apps.analytics.tasks.unix_time')
    @patch('corehq.apps.analytics.tasks.datetime')
    @patch('corehq.apps.analytics.tasks._track_workflow_task')
    @patch('corehq.apps.analytics.tasks.notify_exception')
    def test_track_workflow_throws_exception(self, mock_notify_exception, mock__track_workflow_task,
                                             mock_datetime, mock_unix_time, mock_analytics_enabled_for_email):
        mock_analytics_enabled_for_email.return_value = True
        mock__track_workflow_task.delay.side_effect = [Exception]

        track_workflow('email', 'event')

        self.assertEqual(mock_analytics_enabled_for_email.call_count, 1)
        self.assertEqual(mock_unix_time.call_count, 1)
        self.assertEqual(mock_datetime.utcnow.call_count, 1)
        self.assertEqual(mock__track_workflow_task.delay.call_count, 1)
        self.assertEqual(mock_notify_exception.call_count, 1)

    @patch('corehq.apps.analytics.tasks.analytics_enabled_for_email')
    @patch('corehq.apps.analytics.tasks.unix_time')
    @patch('corehq.apps.analytics.tasks.datetime')
    @patch('corehq.apps.analytics.tasks._track_workflow_task')
    @patch('corehq.apps.analytics.tasks.notify_exception')
    def test_track_workflow_success(self, mock_notify_exception, mock__track_workflow_task,
                                    mock_datetime, mock_unix_time, mock_analytics_enabled_for_email):
        mock_analytics_enabled_for_email.return_value = True

        track_workflow('email', 'event')

        self.assertEqual(mock_analytics_enabled_for_email.call_count, 1)
        self.assertEqual(mock_unix_time.call_count, 1)
        self.assertEqual(mock_datetime.utcnow.call_count, 1)
        self.assertEqual(mock__track_workflow_task.delay.call_count, 1)
        self.assertEqual(mock_notify_exception.call_count, 0)

    @patch('corehq.apps.analytics.tasks.settings')
    @patch('corehq.apps.analytics.tasks.KISSmetrics')
    @patch('corehq.apps.analytics.tasks._log_response')
    @patch('corehq.apps.analytics.tasks._raise_for_urllib3_response')
    def test__track_workflow_task_no_api_key(self, mock__raise_for_urllib3_response, mock__log_response,
                                             mock_KISSmetrics, mock_settings):
        mock_settings.ANALYTICS_IDS.get.return_value = None
        mock_km = Mock()
        mock_KISSmetrics.Client.return_value = mock_km
        mock_email = 'email'
        mock_event = 'event'

        _track_workflow_task(mock_email, mock_event)

        self.assertEqual(mock_KISSmetrics.Client.call_count, 0)
        self.assertEqual(mock_km.record.call_count, 0)
        self.assertEqual(mock__log_response.call_count, 0)
        self.assertEqual(mock__raise_for_urllib3_response.call_count, 0)

    @patch('corehq.apps.analytics.tasks.settings')
    @patch('corehq.apps.analytics.tasks.KISSmetrics')
    @patch('corehq.apps.analytics.tasks._log_response')
    @patch('corehq.apps.analytics.tasks._raise_for_urllib3_response')
    def test__track_workflow_task_with_api_key_no_properties(self, mock__raise_for_urllib3_response, mock__log_response,
                                                             mock_KISSmetrics, mock_settings):
        mock_settings.ANALYTICS_IDS.get.return_value = 'API'
        mock_km = Mock()
        mock_KISSmetrics.Client.return_value = mock_km
        mock_res = Mock()
        mock_km.record.return_value = mock_res
        mock_email = 'email'
        mock_event = 'event'
        mock_dict = {
            'email': mock_email,
            'event': mock_event,
            'properties': None,
            'timestamp': 0
        }

        _track_workflow_task(mock_email, mock_event)

        self.assertEqual(mock_KISSmetrics.Client.call_count, 1)
        mock_KISSmetrics.Client.assert_called_with(key='API')
        self.assertEqual(mock_km.record.call_count, 1)
        mock_km.record.assert_called_with(mock_email, mock_event, {}, 0)
        self.assertEqual(mock__log_response.call_count, 1)
        mock__log_response.assert_called_with('KM', mock_dict, mock_res)
        self.assertEqual(mock__raise_for_urllib3_response.call_count, 1)
        mock__raise_for_urllib3_response.assert_called_with(mock_res)

    @patch('corehq.apps.analytics.tasks.settings')
    @patch('corehq.apps.analytics.tasks.KISSmetrics')
    @patch('corehq.apps.analytics.tasks._log_response')
    @patch('corehq.apps.analytics.tasks._raise_for_urllib3_response')
    def test__track_workflow_task_with_api_key_with_properties(self, mock__raise_for_urllib3_response,
                                                               mock__log_response, mock_KISSmetrics, mock_settings):
        mock_settings.ANALYTICS_IDS.get.return_value = 'API'
        mock_km = Mock()
        mock_KISSmetrics.Client.return_value = mock_km
        mock_res = Mock()
        mock_km.record.return_value = mock_res
        mock_email = 'email'
        mock_event = 'event'
        mock_properties = {'key': 'value'}
        mock_dict = {
            'email': mock_email,
            'event': mock_event,
            'properties': mock_properties,
            'timestamp': 0
        }

        _track_workflow_task(mock_email, mock_event, properties=mock_properties)

        self.assertEqual(mock_KISSmetrics.Client.call_count, 1)
        mock_KISSmetrics.Client.assert_called_with(key='API')
        self.assertEqual(mock_km.record.call_count, 1)
        mock_km.record.assert_called_with(
            mock_email, mock_event, {k.encode('utf-8'): v.encode('utf-8') for k, v in mock_properties.items()}, 0
        )
        self.assertEqual(mock__log_response.call_count, 1)
        mock__log_response.assert_called_with('KM', mock_dict, mock_res)
        self.assertEqual(mock__raise_for_urllib3_response.call_count, 1)
        mock__raise_for_urllib3_response.assert_called_with(mock_res)

    @patch('corehq.apps.analytics.tasks.settings')
    @patch('corehq.apps.analytics.tasks.analytics_enabled_for_email')
    @patch('corehq.apps.analytics.tasks.KISSmetrics')
    @patch('corehq.apps.analytics.tasks._log_response')
    @patch('corehq.apps.analytics.tasks._raise_for_urllib3_response')
    def test_identify_no_api_key(self, mock__raise_for_urllib3_response, mock__log_response, mock_KISSmetrics,
                                 mock_analytics_enabled_for_email, mock_settings):
        mock_settings.ANALYTICS_IDS.get.return_value = None
        mock_km = Mock()
        mock_KISSmetrics.Client.return_value = mock_km
        mock_res = Mock()
        mock_km.set.return_value = mock_res
        mock_email = 'email'
        mock_properties = 'properties'

        identify(mock_email, mock_properties)

        self.assertEqual(mock_analytics_enabled_for_email.call_count, 0)
        self.assertEqual(mock_KISSmetrics.Client.call_count, 0)
        self.assertEqual(mock_km.set.call_count, 0)
        self.assertEqual(mock__log_response.call_count, 0)
        self.assertEqual(mock__raise_for_urllib3_response.call_count, 0)

    @patch('corehq.apps.analytics.tasks.settings')
    @patch('corehq.apps.analytics.tasks.analytics_enabled_for_email')
    @patch('corehq.apps.analytics.tasks.KISSmetrics')
    @patch('corehq.apps.analytics.tasks._log_response')
    @patch('corehq.apps.analytics.tasks._raise_for_urllib3_response')
    def test_identify_with_api_key_no_analytics_enabled(self, mock__raise_for_urllib3_response, mock__log_response,
                                                        mock_KISSmetrics, mock_analytics_enabled_for_email,
                                                        mock_settings):
        mock_settings.ANALYTICS_IDS.get.return_value = 'API'
        mock_analytics_enabled_for_email.return_value = None
        mock_km = Mock()
        mock_KISSmetrics.Client.return_value = mock_km
        mock_res = Mock()
        mock_km.set.return_value = mock_res
        mock_email = 'email'
        mock_properties = 'properties'

        identify(mock_email, mock_properties)

        self.assertEqual(mock_analytics_enabled_for_email.call_count, 1)
        mock_analytics_enabled_for_email.assert_called_with(mock_email)
        self.assertEqual(mock_KISSmetrics.Client.call_count, 0)
        self.assertEqual(mock_km.set.call_count, 0)
        self.assertEqual(mock__log_response.call_count, 0)
        self.assertEqual(mock__raise_for_urllib3_response.call_count, 0)

    @patch('corehq.apps.analytics.tasks.settings')
    @patch('corehq.apps.analytics.tasks.analytics_enabled_for_email')
    @patch('corehq.apps.analytics.tasks.KISSmetrics')
    @patch('corehq.apps.analytics.tasks._log_response')
    @patch('corehq.apps.analytics.tasks._raise_for_urllib3_response')
    def test_identify_with_api_key_and_analytics_enabled(self, mock__raise_for_urllib3_response, mock__log_response,
                                                         mock_KISSmetrics, mock_analytics_enabled_for_email,
                                                         mock_settings):
        mock_settings.ANALYTICS_IDS.get.return_value = 'API'
        mock_analytics_enabled_for_email.return_value = True
        mock_km = Mock()
        mock_KISSmetrics.Client.return_value = mock_km
        mock_res = Mock()
        mock_km.set.return_value = mock_res
        mock_email = 'email'
        mock_properties = 'properties'
        mock_dict = {
            'email': mock_email,
            'properties': mock_properties,
        }

        identify(mock_email, mock_properties)

        self.assertEqual(mock_analytics_enabled_for_email.call_count, 1)
        mock_analytics_enabled_for_email.assert_called_with(mock_email)
        self.assertEqual(mock_KISSmetrics.Client.call_count, 1)
        mock_KISSmetrics.Client.assert_called_with(key='API')
        self.assertEqual(mock_km.set.call_count, 1)
        mock_km.set.return_value(mock_email, mock_properties)
        self.assertEqual(mock__log_response.call_count, 1)
        mock__log_response.assert_called_with('KM', mock_dict, mock_res)
        self.assertEqual(mock__raise_for_urllib3_response.call_count, 1)
        mock__raise_for_urllib3_response.assert_called_with(mock_res)

    @patch('corehq.apps.analytics.tasks.settings')
    @patch('corehq.apps.analytics.tasks.date')
    @patch('corehq.apps.analytics.tasks.timedelta')
    @patch('corehq.apps.analytics.tasks.UserES')
    @patch('corehq.apps.analytics.tasks.math')
    @patch('corehq.apps.analytics.tasks.FormES')
    @patch('corehq.apps.analytics.tasks.get_instance_string')
    @patch('corehq.apps.analytics.tasks._email_is_valid')
    @patch('corehq.apps.analytics.tasks._get_export_count')
    @patch('corehq.apps.analytics.tasks.get_domains_created_by_user')
    @patch('corehq.apps.analytics.tasks.json')
    @patch('corehq.apps.analytics.tasks.submit_data_to_hub_and_kiss')
    @patch('corehq.apps.analytics.tasks.update_datadog_metrics')
    def test_track_periodic_data_return_none(self, mock_update_datadog_metrics, mock_submit_data_to_hub_and_kiss,
                                             mock_json, mock_get_domains_created_by_user, mock__get_export_count,
                                             mock__email_is_valid, mock_get_instance_string, mock_FormES, mock_math,
                                             mock_UserES, mock_timedelta, mock_date, mock_settings):
        mock_settings.ANALYTICS_IDS.get.return_value = False

        response = track_periodic_data()

        self.assertEqual(mock_date.retunr_value.today.call_count, 0)
        self.assertEqual(mock_timedelta.call_count, 0)
        self.assertEqual(mock_UserES
                         .web_users.return_value
                         .last_logged_in.return_value
                         .sort.return_value
                         .source.return_value
                         .analytics_enabled.call_count, 0)
        self.assertEqual(mock_math.ceil.call_count, 0)
        self.assertEqual(mock_FormES
                         .terms_aggregation.return_value
                         .size.return_value
                         .run.return_value
                         .aggregations.domain.return_value
                         .counts_by_bucket.call_count, 0)
        self.assertEqual(mock_UserES
                         .mobile_users.return_value
                         .terms_aggregation.return_value
                         .size.return_value
                         .run.return_value
                         .aggregations.return_value
                         .domain.return_value
                         .counts_by_bucket.call_count, 0)
        self.assertEqual(mock_get_instance_string.call_count, 0)
        self.assertEqual(mock__email_is_valid.call_count, 0)
        self.assertEqual(mock__get_export_count.call_count, 0)
        self.assertEqual(mock_get_domains_created_by_user.call_count, 0)
        self.assertEqual(mock_json.call_count, 0)
        self.assertEqual(mock_submit_data_to_hub_and_kiss.call_count, 0)
        self.assertEqual(mock_update_datadog_metrics.call_count, 0)
        self.assertEqual(response, None)

    @patch('corehq.apps.analytics.tasks.validate_email')
    @patch('corehq.apps.analytics.tasks.logger')
    def test__email_is_valid_no_email(self, mock_logger, mock_validate_email):
        response = _email_is_valid(None)

        self.assertEqual(mock_logger.warn.call_count, 0)
        self.assertEqual(mock_validate_email.call_count, 0)
        self.assertFalse(response)

    @patch('corehq.apps.analytics.tasks.validate_email')
    @patch('corehq.apps.analytics.tasks.logger')
    def test__email_is_valid_email_not_valid(self, mock_logger, mock_validate_email):
        mock_validate_email.side_effect = [EmailNotValidError]

        response = _email_is_valid('email')

        self.assertEqual(mock_logger.warn.call_count, 1)
        self.assertEqual(mock_validate_email.call_count, 1)
        self.assertFalse(response)

    @patch('corehq.apps.analytics.tasks.validate_email')
    @patch('corehq.apps.analytics.tasks.logger')
    def test__email_is_valid_email_success(self, mock_logger, mock_validate_email):
        response = _email_is_valid('email')

        self.assertEqual(mock_logger.warn.call_count, 0)
        self.assertEqual(mock_validate_email.call_count, 1)
        self.assertTrue(response)

    @patch('corehq.apps.analytics.tasks.json')
    @patch('corehq.apps.analytics.tasks.date')
    @patch('corehq.apps.analytics.tasks.csv')
    @patch('corehq.apps.analytics.tasks.time')
    @patch('corehq.apps.analytics.tasks.settings')
    @patch('corehq.apps.analytics.tasks.tinys3')
    @patch('corehq.apps.analytics.tasks.os')
    def test__track_periodic_data_on_kiss_insufficient_settings_arguments(self, mock_os, mock_tinys3,
                                                                          mock_settings, mock_time, mock_csv, mock_date,
                                                                          mock_json):
        mock_periodic_data_list = [{
            'properties': [
                {'property': 'one', 'value': [1]},
            ],
            'email': 'I\'m email',
        }]
        mock_csvwriter = Mock()
        mock_s3_connection = Mock()

        mock_json.loads.return_value = mock_periodic_data_list
        mock_csv.writer.return_value = mock_csvwriter
        mock_settings.S3_ACCESS_KEY = mock_settings.S3_SECRET_KEY = mock_settings.ANALYTICS_IDS.get.return_value = None
        mock_tinys3.Connection.return_value = mock_s3_connection

        with patch('corehq.apps.analytics.tasks.open') as mock_open:
            _track_periodic_data_on_kiss('json')

            self.assertEqual(mock_open.call_count, 1)

        self.assertEqual(mock_date.today.return_value.strftime.call_count, 1)
        self.assertEqual(mock_time.time.call_count, 1)
        self.assertEqual(mock_csvwriter.writerow.call_count, 2)
        self.assertEqual(mock_tinys3.Connection.call_count, 0)
        self.assertEqual(mock_s3_connection.upload.call_count, 0)
        self.assertEqual(mock_os.remove.call_count, 1)

    @patch('corehq.apps.analytics.tasks.json')
    @patch('corehq.apps.analytics.tasks.date')
    @patch('corehq.apps.analytics.tasks.csv')
    @patch('corehq.apps.analytics.tasks.time')
    @patch('corehq.apps.analytics.tasks.settings')
    @patch('corehq.apps.analytics.tasks.tinys3')
    @patch('corehq.apps.analytics.tasks.os')
    def test__track_periodic_data_on_kiss_sufficient_settings_arguments(self, mock_os, mock_tinys3,
                                                                        mock_settings, mock_time, mock_csv, mock_date,
                                                                        mock_json):
        mock_periodic_data_list = [{
            'properties': [
                {'property': 'one', 'value': [1]},
            ],
            'email': 'I\'m email',
        }]
        mock_csvwriter = Mock()
        mock_s3_connection = Mock()

        mock_json.loads.return_value = mock_periodic_data_list
        mock_csv.writer.return_value = mock_csvwriter
        mock_settings.S3_ACCESS_KEY = mock_settings.S3_SECRET_KEY = mock_settings.ANALYTICS_IDS.get.return_value = True
        mock_tinys3.Connection.return_value = mock_s3_connection

        with patch('corehq.apps.analytics.tasks.open') as mock_open:
            _track_periodic_data_on_kiss('json')

            self.assertEqual(mock_open.call_count, 2)

        self.assertEqual(mock_date.today.return_value.strftime.call_count, 1)
        self.assertEqual(mock_time.time.call_count, 1)
        self.assertEqual(mock_csvwriter.writerow.call_count, 2)
        self.assertEqual(mock_tinys3.Connection.call_count, 1)
        self.assertEqual(mock_s3_connection.upload.call_count, 1)
        self.assertEqual(mock_os.remove.call_count, 1)

    @patch('corehq.apps.analytics.tasks.requests')
    @patch('corehq.apps.analytics.tasks.json')
    @patch('corehq.apps.analytics.tasks.logger')
    def test__log_response_exception_not_thrown_status_code_between_400_and_600(self, mock_logger,
                                                                                mock_json, mock_requests):
        mock_response = Mock(status_code=420)
        mock_requests.status_code.return_value = mock_response

        with patch('corehq.apps.analytics.tasks.isinstance', return_value=True) as mock_isinstance:
            _log_response('target', 'data', mock_response)

            self.assertEqual(mock_isinstance.call_count, 1)

        self.assertEqual(mock_json.dumps.call_count, 2)
        self.assertEqual(mock_response.json.call_count, 1)
        self.assertEqual(mock_logger.error.call_count, 1)

        mock_response_text = mock_json.dumps(mock_response.json(), indent=2, sort_keys=True)
        mock_message = 'Sent this data to {target}: {data} \nreceived: {response}'.format(
            target='target',
            data=mock_json.dumps('data', indent=2, sort_keys=True),
            response=mock_response_text
        )

        mock_logger.error.assert_called_with(mock_message)

    @patch('corehq.apps.analytics.tasks.requests')
    @patch('corehq.apps.analytics.tasks.json')
    @patch('corehq.apps.analytics.tasks.logger')
    def test__log_response_throws_exception_status_code_between_400_and_600(self, mock_logger,
                                                                            mock_json, mock_requests):
        mock_response = Mock(status_code=420)
        mock_requests.status_code.return_value = mock_response
        mock_json.dumps.side_effect = [Exception, 'data']

        with patch('corehq.apps.analytics.tasks.isinstance', return_value=True) as mock_isinstance:
            _log_response('target', 'data', mock_response)

            self.assertEqual(mock_isinstance.call_count, 1)

        self.assertEqual(mock_json.dumps.call_count, 2)
        self.assertEqual(mock_response.json.call_count, 1)
        self.assertEqual(mock_logger.error.call_count, 1)

        mock_message = 'Sent this data to {target}: {data} \nreceived: {response}'.format(
            target='target',
            data='data',
            response=mock_response.status_code
        )

        mock_logger.error.assert_called_with(mock_message)

    @patch('corehq.apps.analytics.tasks.requests')
    @patch('corehq.apps.analytics.tasks.json')
    @patch('corehq.apps.analytics.tasks.logger')
    def test__log_response_exception_not_thrown_status_code_not_between_400_and_600(self, mock_logger,
                                                                                    mock_json, mock_requests):
        mock_response = Mock(status_code=123)
        mock_requests.status_code.return_value = mock_response

        with patch('corehq.apps.analytics.tasks.isinstance', return_value=True) as mock_isinstance:
            _log_response('target', 'data', mock_response)

            self.assertEqual(mock_isinstance.call_count, 1)

        self.assertEqual(mock_json.dumps.call_count, 2)
        self.assertEqual(mock_response.json.call_count, 1)
        self.assertEqual(mock_logger.debug.call_count, 1)

        mock_response_text = mock_json.dumps(mock_response.json(), indent=2, sort_keys=True)
        mock_message = 'Sent this data to {target}: {data} \nreceived: {response}'.format(
            target='target',
            data=mock_json.dumps('data', indent=2, sort_keys=True),
            response=mock_response_text
        )

        mock_logger.debug.assert_called_with(mock_message)

    @patch('corehq.apps.analytics.tasks.requests')
    @patch('corehq.apps.analytics.tasks.json')
    @patch('corehq.apps.analytics.tasks.logger')
    def test__log_response_throws_exception_status_code_between_not_400_and_600(self, mock_logger,
                                                                                mock_json, mock_requests):
        mock_response = Mock(status_code=123)
        mock_requests.status_code.return_value = mock_response
        mock_json.dumps.side_effect = [Exception, 'data']

        with patch('corehq.apps.analytics.tasks.isinstance', return_value=True) as mock_isinstance:
            _log_response('target', 'data', mock_response)

            self.assertEqual(mock_isinstance.call_count, 1)

        self.assertEqual(mock_json.dumps.call_count, 2)
        self.assertEqual(mock_response.json.call_count, 1)
        self.assertEqual(mock_logger.debug.call_count, 1)

        mock_message = 'Sent this data to {target}: {data} \nreceived: {response}'.format(
            target='target',
            data='data',
            response=mock_response.status_code
        )

        mock_logger.debug.assert_called_with(mock_message)

    @patch('corehq.apps.analytics.tasks.Domain')
    @patch('corehq.apps.analytics.tasks.WebUser')
    @patch('corehq.apps.analytics.tasks.get_subscription_properties_by_user')
    @patch('corehq.apps.analytics.tasks.update_subscription_properties_by_user')
    def test_update_subscription_properties_by_domain_no_domain_obj(self, mock_update_subscription_properties_by_user,
                                                                    mock_get_subscription_properties_by_user,
                                                                    mock_WebUser, mock_Domain):
        mock_Domain.get_by_name.return_value = None

        update_subscription_properties_by_domain(None)

        self.assertEqual(mock_WebUser.view.all.call_count, 0)
        self.assertEqual(mock_get_subscription_properties_by_user.call_count, 0)
        self.assertEqual(mock_update_subscription_properties_by_user.call_count, 0)

    @patch('corehq.apps.analytics.tasks.Domain')
    @patch('corehq.apps.analytics.tasks.WebUser')
    @patch('corehq.apps.analytics.tasks.get_subscription_properties_by_user')
    @patch('corehq.apps.analytics.tasks.update_subscription_properties_by_user')
    def test_update_subscription_properties_by_domain_with_domain_obj(self, mock_update_subscription_properties_by_user,
                                                                      mock_get_subscription_properties_by_user,
                                                                      mock_WebUser, mock_Domain):
        mock_webuser_one, mock_webuser_two = Mock(), Mock()
        mock_WebUser.view.return_value.all.return_value = [mock_webuser_one, mock_webuser_two]
        mock_get_subscription_properties_by_user.side_effect = ['property_1', 'property_2']

        mock_Domain.get_by_name.return_value = 'domain_obj'

        update_subscription_properties_by_domain('domain')

        self.assertEqual(mock_WebUser.view.return_value.all.call_count, 1)
        self.assertEqual(mock_get_subscription_properties_by_user.call_count, 2)
        self.assertEqual(mock_update_subscription_properties_by_user.delay.call_count, 2)

    @patch('corehq.apps.analytics.tasks.WebUser')
    @patch('corehq.apps.analytics.tasks.identify')
    @patch('corehq.apps.analytics.tasks.update_hubspot_properties')
    def test_update_subscription_properties_by_user(self, mock_update_hubspot_properties, mock_identify, mock_WebUser):
        mock_webuser = Mock(username='username')
        mock_WebUser.get_by_user_id.return_value = mock_webuser
        mock_properties = 'properties'
        mock_id = 'id_1'

        update_subscription_properties_by_user(mock_id, mock_properties)

        self.assertEqual(mock_WebUser.get_by_user_id.call_count, 1)
        mock_WebUser.get_by_user_id.assert_called_with(mock_id)
        self.assertEqual(mock_identify.call_count, 1)
        mock_identify.assert_called_with(mock_webuser.username, mock_properties)
        self.assertEqual(mock_update_hubspot_properties.call_count, 1)
        mock_update_hubspot_properties.assert_called_with(mock_webuser, mock_properties)
