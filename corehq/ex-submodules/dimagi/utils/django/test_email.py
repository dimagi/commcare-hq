from unittest.mock import patch
from django.conf import settings
from django.test import TestCase

from dimagi.utils.django.email import (
    DefaultEmailConfiguration,
    CustomEmailConfiguration,
    get_email_configuration
)
from corehq.apps.email.models import EmailSettings


class TestEmailConfiguration(TestCase):

    def setUp(self):
        self.email_setting1 = EmailSettings.objects.create(
            domain="example1.com",
            username="username1",
            password="password1",
            server="mail.example.com",
            port=587,
            from_email="test1@example.com",
            use_this_gateway=True,
            use_tracking_headers=True,
            sns_secret="secret1",
            ses_config_set_name="config1"
        )

        self.email_setting2 = EmailSettings.objects.create(
            domain="example2.com",
            username="testuser2",
            password="testpassword2",
            server="mail.example.com",
            port=587,
            from_email="test2@example.com",
            use_this_gateway=False,
            use_tracking_headers=False,
            sns_secret="secret2",
            ses_config_set_name="config2"
        )

        self.mock_django_get_connection = patch('dimagi.utils.django.email.django_get_connection').start()
        self.addCleanup(self.mock_django_get_connection.stop)

    def test_get_email_configuration_with_domain_gateway(self):
        config = get_email_configuration("example1.com")
        backend_settings = {
            'host': "mail.example.com",
            'port': 587,
            'username': "username1",
            'password': "password1",
            'use_tls': True,
        }
        self._check_configuration(config, CustomEmailConfiguration, "test1@example.com", "config1",
                                  backend_settings)

    def test_get_email_configuration_with_domain_gateway_disabled(self):
        config = get_email_configuration("example1.com", use_domain_gateway=False)
        self._check_configuration(config, DefaultEmailConfiguration, settings.DEFAULT_FROM_EMAIL,
                                  settings.SES_CONFIGURATION_SET)

    def test_get_email_configuration_without_domain_gateway(self):
        config = get_email_configuration("example2.com", use_domain_gateway=False)
        self._check_configuration(config, DefaultEmailConfiguration, settings.DEFAULT_FROM_EMAIL,
                                  settings.SES_CONFIGURATION_SET)

    def test_get_email_configuration_nonexistent_domain_gateway(self):
        config = get_email_configuration("nonexistent.com")
        self._check_configuration(config, DefaultEmailConfiguration, settings.DEFAULT_FROM_EMAIL,
                                  settings.SES_CONFIGURATION_SET)

    def _check_configuration(self, config: EmailSettings, instance_type,
                             from_email, ses_config_set, backend_settings=None):
        self.assertIsInstance(config, instance_type)
        self.assertEqual(config.from_email, from_email)
        self.assertEqual(config.SES_configuration_set, ses_config_set)
        config.connection()
        if backend_settings:
            backend = "django.core.mail.backends.smtp.EmailBackend"
            self.mock_django_get_connection.assert_called_once_with(backend=backend,
                                                                    **backend_settings)
        else:
            self.mock_django_get_connection.assert_called_once_with()
