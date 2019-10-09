from unittest.case import TestCase
from unittest.mock import Mock, patch

from corehq.apps.analytics.utils import (
    get_meta,
    get_instance_string
)


class TestUtils(TestCase):

    def test_get_meta(self):
        mock_request = Mock()
        mock_request.META.get.side_effect = ['one', 'two']

        response = get_meta(mock_request)
        expected_response = {
            'HTTP_X_FORWARDED_FOR': 'one',
            'REMOTE_ADDR': 'two',
        }

        self.assertEqual(response, expected_response)

    @patch('corehq.apps.analytics.utils.settings')
    def test_get_instance_string_instance_equals_www(self, mock_settings):
        mock_instance = 'www'
        mock_settings.ANALYTICS_CONFIG.get.return_value = mock_instance

        response = get_instance_string()
        expected_response = ''

        self.assertEqual(response, expected_response)

    @patch('corehq.apps.analytics.utils.settings')
    def test_get_instance_string_instance_not_equal_to_www(self, mock_settings):
        mock_instance = 'not www'
        mock_settings.ANALYTICS_CONFIG.get.return_value = mock_instance

        response = get_instance_string()
        expected_response = mock_instance + '_'

        self.assertEqual(response, expected_response)
