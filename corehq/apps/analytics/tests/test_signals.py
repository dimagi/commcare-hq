from unittest.case import TestCase
from unittest.mock import Mock, patch

from corehq.apps.analytics.signals import user_save_callback, domain_save_callback, get_domain_membership_properties, \
    track_user_login


class TestSignals(TestCase):

    @patch('corehq.apps.analytics.signals.get_subscription_properties_by_user')
    @patch('corehq.apps.analytics.signals.get_domain_membership_properties')
    @patch('corehq.apps.analytics.signals.identify')
    @patch('corehq.apps.analytics.signals.update_hubspot_properties')
    def test_user_save_callback_no_couch_user(self, mock_update_hubspot_properties, mock_identify,
                                              mock_get_domain_membership_properties,
                                              mock_get_subscription_properties_by_user):
        user_save_callback('sender')

        self.assertEqual(mock_get_subscription_properties_by_user.call_count, 0)
        self.assertEqual(mock_get_domain_membership_properties.call_count, 0)
        self.assertEqual(mock_identify.delay.call_count, 0)
        self.assertEqual(mock_update_hubspot_properties.delay.call_count, 0)

    @patch('corehq.apps.analytics.signals.get_subscription_properties_by_user')
    @patch('corehq.apps.analytics.signals.get_domain_membership_properties')
    @patch('corehq.apps.analytics.signals.identify')
    @patch('corehq.apps.analytics.signals.update_hubspot_properties')
    def test_user_save_callback_couch_user_is_not_web_user(self, mock_update_hubspot_properties, mock_identify,
                                                           mock_get_domain_membership_properties,
                                                           mock_get_subscription_properties_by_user):
        mock_couch_user = Mock()
        mock_couch_user.is_web_user.return_value = False

        user_save_callback('sender', couch_user=mock_couch_user)

        self.assertEqual(mock_couch_user.is_web_user.call_count, 1)
        self.assertEqual(mock_get_subscription_properties_by_user.call_count, 0)
        self.assertEqual(mock_get_domain_membership_properties.call_count, 0)
        self.assertEqual(mock_identify.delay.call_count, 0)
        self.assertEqual(mock_update_hubspot_properties.delay.call_count, 0)

    @patch('corehq.apps.analytics.signals.get_subscription_properties_by_user')
    @patch('corehq.apps.analytics.signals.get_domain_membership_properties')
    @patch('corehq.apps.analytics.signals.identify')
    @patch('corehq.apps.analytics.signals.update_hubspot_properties')
    def test_user_save_callback_couch_user_is_web_user(self, mock_update_hubspot_properties, mock_identify,
                                                       mock_get_domain_membership_properties,
                                                       mock_get_subscription_properties_by_user):
        mock_couch_user = Mock(username='Lord Nesquik')
        mock_couch_user.is_web_user.return_value = True
        mock_property_one, mock_property_two = {'key_one': 'value_one'}, {'key_two': 'value_two'}
        mock_get_subscription_properties_by_user.return_value = mock_property_one
        mock_get_domain_membership_properties.return_value = mock_property_two
        mock_properties = {
            'key_one': 'value_one',
            'key_two': 'value_two',
        }

        user_save_callback('sender', couch_user=mock_couch_user)

        self.assertEqual(mock_couch_user.is_web_user.call_count, 1)
        self.assertEqual(mock_get_subscription_properties_by_user.call_count, 1)
        mock_get_subscription_properties_by_user.assert_called_with(mock_couch_user)
        self.assertEqual(mock_get_domain_membership_properties.call_count, 1)
        mock_get_domain_membership_properties.assert_called_with(mock_couch_user)
        self.assertEqual(mock_identify.delay.call_count, 1)
        mock_identify.delay.assert_called_with(mock_couch_user.username, mock_properties)
        self.assertEqual(mock_update_hubspot_properties.delay.call_count, 1)
        mock_update_hubspot_properties.delay.assert_called_with(mock_couch_user, mock_properties)

    @patch('corehq.apps.analytics.signals.update_subscription_properties_by_domain')
    def test_domain_save_callback_domain_is_str(self, mock_update_subscription_properties_by_domain):
        mock_domain = 'domain'

        with patch('corehq.apps.analytics.signals.isinstance', return_value=True) as mock_isinstance:
            domain_save_callback('sender', mock_domain)

            self.assertEqual(mock_isinstance.call_count, 1)
            mock_isinstance.assert_called_with(mock_domain, str)

        self.assertEqual(mock_update_subscription_properties_by_domain.call_count, 1)
        mock_update_subscription_properties_by_domain.assert_called_with(mock_domain)

    @patch('corehq.apps.analytics.signals.update_subscription_properties_by_domain')
    def test_domain_save_callback_domain_is_not_str(self, mock_update_subscription_properties_by_domain):
        mock_domain = Mock(name='domain')

        with patch('corehq.apps.analytics.signals.isinstance', return_value=False) as mock_isinstance:
            domain_save_callback('sender', mock_domain)

            self.assertEqual(mock_isinstance.call_count, 1)
            mock_isinstance.assert_called_with(mock_domain, str)

        self.assertEqual(mock_update_subscription_properties_by_domain.call_count, 1)
        mock_update_subscription_properties_by_domain.assert_called_with(mock_domain.name)

    @patch('corehq.apps.analytics.signals.get_instance_string')
    def test_get_domain_membership_properties(self, mock_get_instance_string):
        mock_env = 'env_'
        mock_get_instance_string.return_value = mock_env
        mock_couch_user = Mock(domains=['domain'])

        with patch('corehq.apps.analytics.signals.len', return_value=1) as mock_len:
            response = get_domain_membership_properties(mock_couch_user)

            self.assertEqual(mock_len.call_count, 1)
            mock_len.assert_called_with(mock_couch_user.domains)

        expected_response = {
            'env_number_of_project_spaces': 1,
            'env_project_spaces_list': 'domain',
        }

        self.assertEqual(mock_get_instance_string.call_count, 1)
        self.assertEqual(response, expected_response)

    @patch('corehq.apps.analytics.signals.settings')
    @patch('corehq.apps.analytics.signals.CouchUser')
    @patch('corehq.apps.analytics.signals.reverse')
    @patch('corehq.apps.analytics.signals.ProcessRegistrationView')
    @patch('corehq.apps.analytics.signals._no_cookie_soft_assert')
    @patch('corehq.apps.analytics.signals.get_meta')
    @patch('corehq.apps.analytics.signals.track_user_sign_in_on_hubspot')
    def test_track_user_login_no_hubspot_api_id(self, mock_track_user_sign_in_on_hubspot, mock_get_meta,
                                                mock__no_cookie_soft_assert, mock_ProcessRegistrationView, mock_reverse,
                                                mock_CouchUser, mock_settings):
        mock_request = Mock()
        mock_settings.ANALYTICS_IDS.get.return_value = None

        track_user_login('sender', mock_request, 'user')

        self.assertEqual(mock_CouchUser.from_django_user.call_count, 0)
        self.assertEqual(mock_request.path.startswith.call_count, 0)
        self.assertEqual(mock_reverse.call_count, 0)
        self.assertEqual(mock__no_cookie_soft_assert.call_count, 0)
        self.assertEqual(mock_get_meta.call_count, 0)
        self.assertEqual(mock_track_user_sign_in_on_hubspot.delay.call_count, 0)

    @patch('corehq.apps.analytics.signals.settings')
    @patch('corehq.apps.analytics.signals.CouchUser')
    @patch('corehq.apps.analytics.signals.reverse')
    @patch('corehq.apps.analytics.signals.ProcessRegistrationView')
    @patch('corehq.apps.analytics.signals._no_cookie_soft_assert')
    @patch('corehq.apps.analytics.signals.get_meta')
    @patch('corehq.apps.analytics.signals.track_user_sign_in_on_hubspot')
    def test_track_user_login_no_couch_user(self, mock_track_user_sign_in_on_hubspot, mock_get_meta,
                                            mock__no_cookie_soft_assert, mock_ProcessRegistrationView, mock_reverse,
                                            mock_CouchUser, mock_settings):
        mock_request = Mock()
        mock_settings.ANALYTICS_IDS.get.return_value = True
        mock_CouchUser.from_django_user.return_value = None

        track_user_login('sender', mock_request, 'user')

        self.assertEqual(mock_CouchUser.from_django_user.call_count, 1)
        mock_CouchUser.from_django_user.assert_called_with('user')
        self.assertEqual(mock_request.path.startswith.call_count, 0)
        self.assertEqual(mock_reverse.call_count, 0)
        self.assertEqual(mock__no_cookie_soft_assert.call_count, 0)
        self.assertEqual(mock_get_meta.call_count, 0)
        self.assertEqual(mock_track_user_sign_in_on_hubspot.delay.call_count, 0)

    @patch('corehq.apps.analytics.signals.settings')
    @patch('corehq.apps.analytics.signals.CouchUser')
    @patch('corehq.apps.analytics.signals.reverse')
    @patch('corehq.apps.analytics.signals.ProcessRegistrationView')
    @patch('corehq.apps.analytics.signals._no_cookie_soft_assert')
    @patch('corehq.apps.analytics.signals.get_meta')
    @patch('corehq.apps.analytics.signals.track_user_sign_in_on_hubspot')
    def test_track_user_login_couch_user_is_not_web_user(self, mock_track_user_sign_in_on_hubspot, mock_get_meta,
                                                         mock__no_cookie_soft_assert, mock_ProcessRegistrationView,
                                                         mock_reverse, mock_CouchUser, mock_settings):
        mock_request = Mock()
        mock_settings.ANALYTICS_IDS.get.return_value = True
        mock_couch_user = Mock()
        mock_couch_user.is_web_user.return_value = False
        mock_CouchUser.from_django_user.return_value = mock_couch_user

        track_user_login('sender', mock_request, 'user')

        self.assertEqual(mock_CouchUser.from_django_user.call_count, 1)
        mock_CouchUser.from_django_user.assert_called_with('user')
        self.assertEqual(mock_couch_user.is_web_user.call_count, 1)
        self.assertEqual(mock_request.path.startswith.call_count, 0)
        self.assertEqual(mock_reverse.call_count, 0)
        self.assertEqual(mock__no_cookie_soft_assert.call_count, 0)
        self.assertEqual(mock_get_meta.call_count, 0)
        self.assertEqual(mock_track_user_sign_in_on_hubspot.delay.call_count, 0)

    @patch('corehq.apps.analytics.signals.settings')
    @patch('corehq.apps.analytics.signals.CouchUser')
    @patch('corehq.apps.analytics.signals.reverse')
    @patch('corehq.apps.analytics.signals.ProcessRegistrationView')
    @patch('corehq.apps.analytics.signals._no_cookie_soft_assert')
    @patch('corehq.apps.analytics.signals.get_meta')
    @patch('corehq.apps.analytics.signals.track_user_sign_in_on_hubspot')
    def test_track_user_login_no_user_confirming(self, mock_track_user_sign_in_on_hubspot, mock_get_meta,
                                                 mock__no_cookie_soft_assert, mock_ProcessRegistrationView,
                                                 mock_reverse, mock_CouchUser, mock_settings):
        mock_request = Mock(COOKIES=[])
        mock_request.path.startswith.return_value = None
        mock_settings.ANALYTICS_IDS.get.return_value = True
        mock_couch_user = Mock()
        mock_couch_user.is_web_user.return_value = True
        mock_CouchUser.from_django_user.return_value = mock_couch_user
        mock_ProcessRegistrationView.urlname = 'urlname'

        track_user_login('sender', mock_request, 'user')

        self.assertEqual(mock_CouchUser.from_django_user.call_count, 1)
        mock_CouchUser.from_django_user.assert_called_with('user')
        self.assertEqual(mock_couch_user.is_web_user.call_count, 1)
        self.assertEqual(mock_request.path.startswith.call_count, 1)
        self.assertEqual(mock_reverse.call_count, 1)
        mock_reverse.assert_called_with(mock_ProcessRegistrationView.urlname)
        mock_request.path.startswith.assert_called_with(mock_reverse(mock_ProcessRegistrationView.urlname))
        self.assertEqual(mock__no_cookie_soft_assert.call_count, 0)
        self.assertEqual(mock_get_meta.call_count, 0)
        self.assertEqual(mock_track_user_sign_in_on_hubspot.delay.call_count, 0)

    @patch('corehq.apps.analytics.signals.settings')
    @patch('corehq.apps.analytics.signals.CouchUser')
    @patch('corehq.apps.analytics.signals.reverse')
    @patch('corehq.apps.analytics.signals.ProcessRegistrationView')
    @patch('corehq.apps.analytics.signals._no_cookie_soft_assert')
    @patch('corehq.apps.analytics.signals.get_meta')
    @patch('corehq.apps.analytics.signals.track_user_sign_in_on_hubspot')
    def test_track_user_login_with_user_confirming(self, mock_track_user_sign_in_on_hubspot, mock_get_meta,
                                                   mock__no_cookie_soft_assert, mock_ProcessRegistrationView,
                                                   mock_reverse, mock_CouchUser, mock_settings):
        mock_request = Mock(COOKIES={})
        mock_request.path.startswith.return_value = True
        mock_settings.ANALYTICS_IDS.get.return_value = True
        mock_couch_user = Mock()
        mock_couch_user.is_web_user.return_value = True
        mock_CouchUser.from_django_user.return_value = mock_couch_user
        mock_ProcessRegistrationView.urlname = 'urlname'

        track_user_login('sender', mock_request, 'user')

        self.assertEqual(mock_CouchUser.from_django_user.call_count, 1)
        mock_CouchUser.from_django_user.assert_called_with('user')
        self.assertEqual(mock_couch_user.is_web_user.call_count, 1)
        self.assertEqual(mock_request.path.startswith.call_count, 1)
        self.assertEqual(mock_reverse.call_count, 1)
        mock_reverse.assert_called_with(mock_ProcessRegistrationView.urlname)
        mock_request.path.startswith.assert_called_with(mock_reverse(mock_ProcessRegistrationView.urlname))
        self.assertEqual(mock__no_cookie_soft_assert.call_count, 1)
        self.assertEqual(mock_get_meta.call_count, 1)
        mock_get_meta.assert_called_with(mock_request)
        self.assertEqual(mock_track_user_sign_in_on_hubspot.delay.call_count, 1)
