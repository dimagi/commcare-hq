from unittest.case import TestCase
from unittest.mock import Mock, patch

from corehq.apps.analytics.tasks import HUBSPOT_COOKIE
from corehq.apps.analytics.views import HubspotClickDeployView, GreenhouseCandidateView


class TestHubspotClickDeployView(TestCase):

    @patch('corehq.apps.analytics.views.get_meta')
    @patch('corehq.apps.analytics.views.track_clicked_deploy_on_hubspot')
    def test_post(self, mock_track_clicked_deploy_on_hubspot, mock_get_meta):
        self.mock_request = Mock(couch_user='user')
        self.mock_request.COOKIES.get.return_value = HUBSPOT_COOKIE

        response = HubspotClickDeployView().post(self.mock_request)

        self.assertEqual(mock_get_meta.call_count, 1)
        mock_get_meta.assert_called_with(self.mock_request)
        mock_meta = mock_get_meta(self.mock_request)
        self.assertEqual(mock_track_clicked_deploy_on_hubspot.delay.call_count, 1)
        mock_track_clicked_deploy_on_hubspot.delay.assert_called_with(
            self.mock_request.couch_user, HUBSPOT_COOKIE, mock_meta
        )
        self.assertEqual(response.status_code, 200)


class TestGreenhouseCandidateView(TestCase):

    def setUp(self):
        self.mock_request = Mock()

    @patch('corehq.apps.analytics.views.GreenhouseCandidateView')
    def test_dispatcher(self, mock_greenhouse):
        with patch('corehq.apps.analytics.views.super') as mock_super:
            response = GreenhouseCandidateView().dispatch(self.mock_request)
            expected_response = mock_super(mock_greenhouse, mock_greenhouse).dispatch(self.mock_request)

        self.assertEqual(response, expected_response)

    @patch('corehq.apps.analytics.views.hmac')
    @patch('corehq.apps.analytics.views.settings')
    @patch('corehq.apps.analytics.views.hashlib')
    @patch('corehq.apps.analytics.views.json')
    @patch('corehq.apps.analytics.views.track_job_candidate_on_hubspot')
    def test_post_signature_header_length_not_2(self, mock_track_job_candidate_on_hubspot, mock_json,
                                                mock_hashlib, mock_settings, mock_hmac):
        self.mock_request.META.get.return_value.split.return_value = 'not'
        mock_digester = Mock()
        mock_hmac.new.return_value = mock_digester

        with patch('corehq.apps.analytics.views.isinstance') as mock_isinstance, \
            patch('corehq.apps.analytics.views.len', return_value=1) as mock_len, \
            patch('corehq.apps.analytics.views.str') as mock_str:
            response = GreenhouseCandidateView().post(self.mock_request)

            self.assertEqual(mock_isinstance.call_count, 1)
            mock_isinstance.assert_called_with(mock_settings.GREENHOUSE_API_KEY, mock_str)
            self.assertEqual(mock_len.call_count, 1)
            mock_len.assert_called_with('not')
            self.assertEqual(mock_str.call_count, 0)

        self.assertEqual(mock_hmac.new.call_count, 1)
        self.assertEqual(mock_settings.GREENHOUSE_API_KEY.encode.call_count, 1)
        self.assertEqual(mock_digester.hexdigest.call_count, 1)
        self.assertEqual(self.mock_request.META.get.return_value.split.call_count, 1)
        self.assertEqual(self.mock_request.body.decode.call_count, 0)
        self.assertEqual(mock_json.loads.call_count, 0)
        self.assertEqual(mock_track_job_candidate_on_hubspot.delay.call_count, 0)
        self.assertEqual(response.status_code, 200)

    @patch('corehq.apps.analytics.views.hmac')
    @patch('corehq.apps.analytics.views.settings')
    @patch('corehq.apps.analytics.views.hashlib')
    @patch('corehq.apps.analytics.views.json')
    @patch('corehq.apps.analytics.views.track_job_candidate_on_hubspot')
    def test_post_signature_header_length_2(self, mock_track_job_candidate_on_hubspot, mock_json,
                                            mock_hashlib, mock_settings, mock_hmac):
        self.mock_request.META.get.return_value.split.return_value = [2, 2]
        mock_digester = Mock()
        mock_hmac.new.return_value = mock_digester

        with patch('corehq.apps.analytics.views.isinstance') as mock_isinstance, \
            patch('corehq.apps.analytics.views.len', return_value=2) as mock_len, \
            patch('corehq.apps.analytics.views.str', side_effect=['2', '3']) as mock_str:
            response = GreenhouseCandidateView().post(self.mock_request)

            self.assertEqual(mock_isinstance.call_count, 1)
            mock_isinstance.assert_called_with(mock_settings.GREENHOUSE_API_KEY, mock_str)
            self.assertEqual(mock_len.call_count, 1)
            mock_len.assert_called_with([2, 2])
            self.assertEqual(mock_str.call_count, 2)

        self.assertEqual(mock_hmac.new.call_count, 1)
        self.assertEqual(mock_settings.GREENHOUSE_API_KEY.encode.call_count, 1)
        self.assertEqual(mock_digester.hexdigest.call_count, 1)
        self.assertEqual(self.mock_request.META.get.return_value.split.call_count, 1)
        self.assertEqual(self.mock_request.body.decode.call_count, 0)
        self.assertEqual(mock_json.loads.call_count, 0)
        self.assertEqual(mock_track_job_candidate_on_hubspot.delay.call_count, 0)
        self.assertEqual(response.status_code, 200)

    @patch('corehq.apps.analytics.views.hmac')
    @patch('corehq.apps.analytics.views.settings')
    @patch('corehq.apps.analytics.views.hashlib')
    @patch('corehq.apps.analytics.views.json')
    @patch('corehq.apps.analytics.views.track_job_candidate_on_hubspot')
    def test_post_signature_from_request_equals_calculated_signature(self, mock_track_job_candidate_on_hubspot,
                                                                     mock_json, mock_hashlib, mock_settings, mock_hmac):
        self.mock_request.META.get.return_value.split.return_value = [2, 2]
        mock_digester = Mock()
        mock_digester.hexdigest.return_value = 'signature'
        mock_hmac.new.return_value = mock_digester
        mock_json.loads.return_value = {
            'payload': {
                'application': {
                    'candidate': {
                        'email_addresses': [{
                            'value': 'I\'m value'
                        }]
                    }
                }
            }
        }

        with patch('corehq.apps.analytics.views.isinstance') as mock_isinstance, \
            patch('corehq.apps.analytics.views.len', return_value=2) as mock_len, \
            patch('corehq.apps.analytics.views.str', side_effect=['2', '2']) as mock_str:
            response = GreenhouseCandidateView().post(self.mock_request)

            self.assertEqual(mock_isinstance.call_count, 1)
            mock_isinstance.assert_called_with(mock_settings.GREENHOUSE_API_KEY, mock_str)
            self.assertEqual(mock_len.call_count, 1)
            mock_len.assert_called_with([2, 2])
            self.assertEqual(mock_str.call_count, 2)

        self.assertEqual(mock_hmac.new.call_count, 1)
        self.assertEqual(mock_settings.GREENHOUSE_API_KEY.encode.call_count, 1)
        self.assertEqual(mock_digester.hexdigest.call_count, 1)
        self.assertEqual(self.mock_request.META.get.return_value.split.call_count, 1)
        self.assertEqual(self.mock_request.body.decode.call_count, 1)
        self.assertEqual(mock_json.loads.call_count, 1)
        self.assertEqual(mock_track_job_candidate_on_hubspot.delay.call_count, 1)
        self.assertEqual(response.status_code, 200)

    @patch('corehq.apps.analytics.views.hmac')
    @patch('corehq.apps.analytics.views.settings')
    @patch('corehq.apps.analytics.views.hashlib')
    @patch('corehq.apps.analytics.views.json')
    @patch('corehq.apps.analytics.views.track_job_candidate_on_hubspot')
    def test_post_signature_from_request_equals_calculated_signature_keyerror(self, mock_track_job_candidate_on_hubspot,
                                                                              mock_json, mock_hashlib, mock_settings,
                                                                              mock_hmac):
        self.mock_request.META.get.return_value.split.return_value = [2, 2]
        mock_digester = Mock()
        mock_digester.hexdigest.return_value = 'signature'
        mock_hmac.new.return_value = mock_digester
        mock_json.loads.return_value = {
            'payload': {
                'application': {
                    'candidate': {
                        'email_addresses': [{
                            'value': 'I\'m value'
                        }]
                    }
                }
            }
        }
        mock_track_job_candidate_on_hubspot.delay.side_effect = [KeyError]

        with patch('corehq.apps.analytics.views.isinstance') as mock_isinstance, \
            patch('corehq.apps.analytics.views.len', return_value=2) as mock_len, \
            patch('corehq.apps.analytics.views.str', side_effect=['2', '2']) as mock_str:
            response = GreenhouseCandidateView().post(self.mock_request)

            self.assertEqual(mock_isinstance.call_count, 1)
            mock_isinstance.assert_called_with(mock_settings.GREENHOUSE_API_KEY, mock_str)
            self.assertEqual(mock_len.call_count, 1)
            mock_len.assert_called_with([2, 2])
            self.assertEqual(mock_str.call_count, 2)

        self.assertEqual(mock_hmac.new.call_count, 1)
        self.assertEqual(mock_settings.GREENHOUSE_API_KEY.encode.call_count, 1)
        self.assertEqual(mock_digester.hexdigest.call_count, 1)
        self.assertEqual(self.mock_request.META.get.return_value.split.call_count, 1)
        self.assertEqual(self.mock_request.body.decode.call_count, 1)
        self.assertEqual(mock_json.loads.call_count, 1)
        self.assertEqual(mock_track_job_candidate_on_hubspot.delay.call_count, 1)
        self.assertEqual(response.status_code, 200)
