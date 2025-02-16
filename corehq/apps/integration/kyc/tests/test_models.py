from django.test import TestCase

import pytest

from corehq.apps.integration.kyc.models import KycConfig, UserDataStore
from corehq.motech.models import ConnectionSettings

DOMAIN = 'test-domain'


class TestGetConnectionSettings(TestCase):

    def test_valid_without_connection_settings(self):
        config = KycConfig(
            domain=DOMAIN,
            user_data_store=UserDataStore.USER_CASE,
        )
        # Does not raise `django.db.utils.IntegrityError`
        config.save()

    def test_get_connection_settings(self):
        config = KycConfig(
            domain=DOMAIN,
            user_data_store=UserDataStore.USER_CASE,
        )
        assert ConnectionSettings.objects.count() == 0

        connx = config.get_connection_settings()
        assert isinstance(connx, ConnectionSettings)
        # First call creates ConnectionSettings
        assert ConnectionSettings.objects.count() == 1

        connx = config.get_connection_settings()
        assert isinstance(connx, ConnectionSettings)
        # Subsequent calls get existing ConnectionSettings
        assert ConnectionSettings.objects.count() == 1

    def test_bad_config(self):
        config = KycConfig(
            domain=DOMAIN,
            user_data_store=UserDataStore.USER_CASE,
            provider='invalid',
        )
        with pytest.raises(
            ValueError,
            match="^Unable to determine connection settings for KYC provider "
                  "'invalid'.$",
        ):
            config.get_connection_settings()
