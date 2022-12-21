from django.test import TestCase

from corehq.motech.const import OAUTH2_PWD
from corehq.motech.models import ConnectionSettings
from corehq.motech.utils import copy_api_auth_settings


class TestApiSettingsMigration(TestCase):
    username = 'terry'
    password = 'wafer-thin_mint'

    def setUp(self):
        self.connx_dhis2 = ConnectionSettings(
            domain='meaning-of-life',
            name='Mr. Creosote',
            url='https://restaurant.fr/api/',
            auth_type=OAUTH2_PWD,
            username=self.username,
            notify_addresses_str='admin@example.com',
            api_auth_settings='dhis2_auth_settings',
        )
        self.connx_dhis2.plaintext_password = self.password
        self.connx_dhis2.save()

    def test_dhis2_connection_updated(self):
        copy_api_auth_settings(self.connx_dhis2)
        self.assertEqual(
            self.connx_dhis2.token_url,
            "https://restaurant.fr/api/uaa/oauth/token"
        )
        self.assertEqual(
            self.connx_dhis2.refresh_url,
            "https://restaurant.fr/api/uaa/oauth/token",
        )
