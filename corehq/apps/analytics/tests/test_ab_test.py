from unittest.case import TestCase
from unittest.mock import Mock, patch

from corehq.apps.analytics.ab_tests import SessionAbTest


class TestSessionAbTest(TestCase):

    def setUp(self):
        self.mock_config = Mock()
        self.mock_request = Mock()

    def test___init___no_session_key(self):
        self.mock_request.session.session_key = None

        session = SessionAbTest(self.mock_config, self.mock_request)

        self.assertEqual(self.mock_request.session.save.call_count, 1)
        self.assertEqual(session.config, self.mock_config)
        self.assertEqual(session.request, self.mock_request)

    def test___init___with_session_key(self):
        self.mock_request.session.session_key = True

        session = SessionAbTest(self.mock_config, self.mock_request)

        self.assertEqual(self.mock_request.session.save.call_count, 0)
        self.assertEqual(session.config, self.mock_config)
        self.assertEqual(session.request, self.mock_request)

    def test__cookie_id(self):
        self.mock_config.slug = 'slug'

        config_id = SessionAbTest(self.mock_config, self.mock_request)._cookie_id
        expected_config_id = 'slug_ab'

        self.assertEqual(config_id, expected_config_id)

    def test__cache_id(self):
        self.mock_config.slug = 'slug'
        self.mock_request.session.session_key = 'key'

        cache_id = SessionAbTest(self.mock_config, self.mock_request)._cache_id
        expected_cache_id = 'slug_ab_key'

        self.assertEqual(cache_id, expected_cache_id)

    @patch('corehq.apps.analytics.ab_tests.cache')
    def test_version_cache_return_none(self, mock_cache):
        self.mock_request.COOKIES = {'cookie_ab': 'cookie_ab'}
        self.mock_config.force_refresh = True
        self.mock_config.slug = 'cookie'
        mock__debug_message = Mock()
        mock_cache_version = Mock()
        mock_cache.get.return_value = None

        session = SessionAbTest(self.mock_config, self.mock_request)
        session._debug_message = mock__debug_message
        session.cache_version = mock_cache_version
        response = session.version(assign_if_blank=False)
        expected_response = None

        self.assertEqual(mock_cache.get.call_count, 1)
        mock_cache.get.assert_called_with(session._cache_id)
        self.assertEqual(mock__debug_message.call_count, 0)
        self.assertEqual(mock_cache_version.call_count, 1)
        mock_cache_version.assert_called_with(expected_response)
        self.assertEqual(response, expected_response)

    @patch('corehq.apps.analytics.ab_tests.cache')
    def test_version_cache_get_true(self, mock_cache):
        mock__debug_message = Mock()
        mock_cache_version = Mock()
        mock_cache.get.return_value = 'not none'

        session = SessionAbTest(self.mock_config, self.mock_request)
        session._debug_message = mock__debug_message
        session.cache_version = mock_cache_version
        response = session.version()
        expected_response = 'not none'

        self.assertEqual(mock_cache.get.call_count, 2)
        mock_cache.get.assert_called_with(session._cache_id)
        self.assertEqual(mock__debug_message.call_count, 1)
        mock__debug_message.assert_called_with("fetched version from cache '{}'".format(expected_response))
        self.assertEqual(mock_cache_version.call_count, 1)
        mock_cache_version.assert_called_with(expected_response)
        self.assertEqual(response, expected_response)

    @patch('corehq.apps.analytics.ab_tests.cache')
    def test_version_cache_get_false(self, mock_cache):
        self.mock_request.COOKIES = {'cookie_ab': 'cookie_ab'}
        self.mock_config.force_refresh = False
        self.mock_config.slug = 'cookie'
        mock__debug_message = Mock()
        mock_cache_version = Mock()
        mock_cache.get.return_value = None

        session = SessionAbTest(self.mock_config, self.mock_request)
        session._debug_message = mock__debug_message
        session.cache_version = mock_cache_version
        response = session.version()
        expected_response = 'cookie_ab'

        self.assertEqual(mock_cache.get.call_count, 1)
        mock_cache.get.assert_called_with(session._cache_id)
        self.assertEqual(mock__debug_message.call_count, 1)
        mock__debug_message.assert_called_with("fetched version from cookie '{}'".format(expected_response))
        self.assertEqual(mock_cache_version.call_count, 1)
        mock_cache_version.assert_called_with(expected_response)
        self.assertEqual(response, expected_response)

    @patch('corehq.apps.analytics.ab_tests.cache')
    @patch('corehq.apps.analytics.ab_tests.random')
    def test_version_assign_if_blink(self, mock_random, mock_cache):
        self.mock_request.COOKIES = {'cookie_ab': 'cookie_ab'}
        self.mock_config.force_refresh = True
        self.mock_config.slug = 'cookie'
        mock__debug_message = Mock()
        mock_cache_version = Mock()
        mock_cache.get.return_value = None
        mock_random.choice.return_value = 'value'

        session = SessionAbTest(self.mock_config, self.mock_request)
        session._debug_message = mock__debug_message
        session.cache_version = mock_cache_version
        response = session.version()
        expected_response = 'value'

        self.assertEqual(mock_cache.get.call_count, 1)
        mock_cache.get.assert_called_with(session._cache_id)
        self.assertEqual(mock_random.choice.call_count, 1)
        self.assertEqual(mock__debug_message.call_count, 1)
        mock__debug_message.assert_called_with("fetched new version '{}'".format(expected_response))
        self.assertEqual(mock_cache_version.call_count, 1)
        mock_cache_version.assert_called_with(expected_response)
        self.assertEqual(response, expected_response)

    @patch('corehq.apps.analytics.ab_tests.cache')
    def test_cache_version(self, mock_cache):
        mock_version = 'version'
        mock__debug_message = Mock()

        session = SessionAbTest(self.mock_config, self.mock_request)
        session._debug_message = mock__debug_message
        session.cache_version(mock_version)

        self.assertEqual(mock__debug_message.call_count, 1)
        mock__debug_message.assert_called_with("cache version '{}' under '{}'".format(mock_version, session._cache_id))
        self.assertEqual(mock_cache.set.call_count, 1)
        mock_cache.set.assert_called_with(session._cache_id, mock_version)

    @patch('corehq.apps.analytics.ab_tests.cache')
    def test__clear_cache(self, mock_cache):
        mock__debug_message = Mock()

        session = SessionAbTest(self.mock_config, self.mock_request)
        session._debug_message = mock__debug_message
        session._clear_cache()

        self.assertEqual(mock__debug_message.call_count, 1)
        mock__debug_message.assert_called_with("clearing cache '{}'".format(session._cache_id))
        self.assertEqual(mock_cache.delete.call_count, 1)
        mock_cache.delete.assert_called_with(session._cache_id)

    @patch('corehq.apps.analytics.ab_tests.logger')
    def test__debug_message_is_debug_false(self, mock_logger):
        self.mock_config.is_debug = False

        session = SessionAbTest(self.mock_config, self.mock_request)
        session._debug_message('message')

        self.assertEqual(mock_logger.info.call_count, 0)

    @patch('corehq.apps.analytics.ab_tests.logger')
    def test__debug_message_is_debug_true(self, mock_logger):
        self.mock_config.is_debug = True
        mock_message = 'message'

        session = SessionAbTest(self.mock_config, self.mock_request)
        session._debug_message(mock_message)

        self.assertEqual(mock_logger.info.call_count, 1)
        mock_logger.info.assert_called_with("SESSION AB TEST [{}]: {}".format(session._cookie_id, mock_message))

    def test_update_response_force_refresh_false(self):
        mock_response = Mock()
        mock__clear_response = Mock()
        mock_version = Mock()
        mock__debug_message = Mock()
        self.mock_config.force_refresh = False

        session = SessionAbTest(self.mock_config, self.mock_request)
        session._clear_response = mock__clear_response
        session.version = mock_version
        session._debug_message = mock__debug_message
        session.update_response(mock_response)

        self.assertEqual(mock__clear_response.call_count, 0)
        self.assertEqual(mock_version.call_count, 1)
        self.assertEqual(mock__debug_message.call_count, 1)
        mock__debug_message.assert_called_with(
            "storing cookie value '{}' in '{}'".format(session.version(), session._cookie_id)
        )
        self.assertEqual(mock_response.set_cookie.call_count, 1)
        mock_response.set_cookie.assert_called_with(session._cookie_id, session.version())

    def test_update_response_force_refresh_true(self):
        mock_response = Mock()
        mock__clear_response = Mock()
        mock_version = Mock()
        mock__debug_message = Mock()
        self.mock_config.force_refresh = True

        session = SessionAbTest(self.mock_config, self.mock_request)
        session._clear_response = mock__clear_response
        session.version = mock_version
        session._debug_message = mock__debug_message
        session.update_response(mock_response)

        self.assertEqual(mock__clear_response.call_count, 1)
        mock__clear_response.assert_called_with(mock_response)
        self.assertEqual(mock_version.call_count, 1)
        self.assertEqual(mock__debug_message.call_count, 1)
        mock__debug_message.assert_called_with(
            "storing cookie value '{}' in '{}'".format(session.version(), session._cookie_id)
        )
        self.assertEqual(mock_response.set_cookie.call_count, 1)
        mock_response.set_cookie.assert_called_with(session._cookie_id, session.version())

    def test_clear_response(self):
        mock_response = Mock()
        mock__debug_message = Mock()

        session = SessionAbTest(self.mock_config, self.mock_request)
        session._debug_message = mock__debug_message
        session._clear_response(mock_response)

        self.assertEqual(mock__debug_message.call_count, 1)
        mock__debug_message.assert_called_with("clearing cookies '{}'".format(session._cookie_id))
        self.assertEqual(mock_response.delete_cookie.call_count, 1)
        mock_response.delete_cookie.assert_called_with(session._cookie_id)

    def test_context_force_refresh_false(self):
        self.mock_config.force_refresh = False
        self.mock_config.name = 'name'
        mock__clear_cache = Mock()
        mock__debug_message = Mock()
        mock_version = Mock(return_value='version')

        session = SessionAbTest(self.mock_config, self.mock_request)
        session._clear_cache = mock__clear_cache
        session.version = mock_version
        session._debug_message = mock__debug_message
        response = session.context
        expected_response = {
            'name': 'name',
            'version': 'version',
        }

        self.assertEqual(mock_version.call_count, 1)
        self.assertEqual(mock__debug_message.call_count, 1)
        mock__debug_message.assert_called_with("Fetching Template Context {}".format(expected_response))
        self.assertEqual(response, expected_response)

    def test_context_force_refresh_true(self):
        self.mock_config.force_refresh = True
        self.mock_config.name = 'name'
        mock__clear_cache = Mock()
        mock__debug_message = Mock()
        mock_version = Mock(return_value='version')

        session = SessionAbTest(self.mock_config, self.mock_request)
        session._clear_cache = mock__clear_cache
        session.version = mock_version
        session._debug_message = mock__debug_message
        response = session.context
        expected_response = {
            'name': 'name',
            'version': 'version',
        }

        self.assertEqual(mock__clear_cache.call_count, 1)
        self.assertEqual(mock_version.call_count, 1)
        self.assertEqual(mock__debug_message.call_count, 1)
        mock__debug_message.assert_called_with("Fetching Template Context {}".format(expected_response))
        self.assertEqual(response, expected_response)
