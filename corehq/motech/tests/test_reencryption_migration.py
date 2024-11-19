from django.test import SimpleTestCase

from corehq.apps.email.models import EmailSettings
from corehq.motech.const import ALGO_AES

from corehq.motech.utils import reencrypt_ecb_to_cbc_mode


class TestReencryptionMigration(SimpleTestCase):
    def setUp(self):
        self.email_settings = EmailSettings(
            domain='example.com',
            username='testuser',
        )
        self.email_settings.plaintext_password = 'testpassword'

    def test_reencrypt_ecb_to_cbc_mode_match_plaintext(self):
        reencrypted_password = reencrypt_ecb_to_cbc_mode(self.email_settings.password, f'${ALGO_AES}$')

        self.email_settings.password_cbc = reencrypted_password

        self.assertEqual(self.email_settings.plaintext_password, self.email_settings.plaintext_password_cbc)

    def test_email_settings_write_to_both_fields(self):
        self.email_settings.plaintext_password = 'testpassword'
        self.email_settings.plaintext_password_cbc = 'testpassword'

        self.assertIsNotNone(self.email_settings.password)
        self.assertIsNotNone(self.email_settings.password_cbc)

        self.assertEqual(self.email_settings.plaintext_password, 'testpassword')
        self.assertEqual(self.email_settings.plaintext_password_cbc, 'testpassword')
