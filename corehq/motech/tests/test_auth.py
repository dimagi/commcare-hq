from django.test import TestCase

from corehq.motech.auth import BasicAuthManager
from corehq.motech.const import ALGO_AES, BASIC_AUTH
from corehq.motech.models import ConnectionSettings


class ConnectionSettingsAuthManagerTests(TestCase):
    username = 'terry'
    password = 'wafer-thin_mint'

    def setUp(self):
        self.connx = ConnectionSettings(
            domain='meaning-of-life',
            name='Mr. Creosote',
            url='https://restaurant.fr/api/',
            auth_type=BASIC_AUTH,
            username=self.username,
            notify_addresses_str='admin@example.com',
        )
        self.connx.plaintext_password = self.password
        self.connx.save()

    def tearDown(self):
        self.connx.delete()

    def test_connection_settings_auth_manager(self):
        auth_manager = self.connx.get_auth_manager()
        self.assertIsInstance(auth_manager, BasicAuthManager)
        self.assertEqual(auth_manager.username, self.username)
        self.assertEqual(auth_manager.password, self.password)
        self.assertNotEqual(auth_manager.password, self.connx.password)
        self.assertTrue(self.connx.password.startswith(f'${ALGO_AES}$'))
