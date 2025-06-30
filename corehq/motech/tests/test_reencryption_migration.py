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

    def test_reencrypt_ecb_to_cbc_mode_match_plaintext_with_prefix(self):
        plaintext_password = 'testpassword'
        self.email_settings.password = self.plaintext_to_ecb_password(plaintext_password, True)
        reencrypted_password = reencrypt_ecb_to_cbc_mode(self.email_settings.password, f'${ALGO_AES}$')

        self.email_settings.password = reencrypted_password

        self.assertEqual(plaintext_password, self.email_settings.plaintext_password)

    def test_reencrypt_ecb_to_cbc_mode_match_plaintext_without_prefix(self):
        plaintext_password = 'testpassword'
        self.email_settings.password = self.plaintext_to_ecb_password(plaintext_password, False)
        reencrypted_password = reencrypt_ecb_to_cbc_mode(self.email_settings.password, f'${ALGO_AES}$')

        self.email_settings.password = reencrypted_password

        self.assertEqual(plaintext_password, self.email_settings.plaintext_password)

    def test_empty_password_reencrypt_ecb_to_cbc_mode_match_plaintext(self):
        plaintext_password = ''
        self.email_settings.password = plaintext_password
        reencrypted_password = reencrypt_ecb_to_cbc_mode(self.email_settings.password, f'${ALGO_AES}$')
        self.email_settings.password = reencrypted_password
        self.assertEqual(plaintext_password, self.email_settings.plaintext_password)
