import doctest
import json
from base64 import b64encode

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from Crypto.Cipher import AES

import corehq.motech.utils
from corehq.motech.utils import (
    AES_BLOCK_SIZE,
    AES_KEY_MAX_LEN,
    b64_aes_decrypt,
    b64_aes_encrypt,
    b64_aes_cbc_encrypt,
    b64_aes_cbc_decrypt,
    get_endpoint_url,
    pformat_json,
    simple_pad,
    unpad,
)


class SimplePadTests(SimpleTestCase):

    def test_assertion(self):
        with self.assertRaises(AssertionError):
            simple_pad('xyzzy', 8, b'*')

    def test_ascii_bytestring_default_char(self):
        padded = simple_pad(b'xyzzy', 8)
        self.assertEqual(padded, b'xyzzy   ')

    def test_nonascii(self):
        """
        pad should pad a string according to its size in bytes, not its length in letters.
        """
        padded = simple_pad(b'xy\xc5\xba\xc5\xbay', 8, b'*')
        self.assertEqual(padded, b'xy\xc5\xba\xc5\xbay*')


class UnpadTests(SimpleTestCase):

    def test_unpad_simple(self):
        unpadded = unpad(b'xyzzy   ')
        self.assertEqual(unpadded, b'xyzzy')

    def test_unpad_crypto(self):
        unpadded = unpad(b'xyzzy\x80\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
        self.assertEqual(unpadded, b'xyzzy')

    def test_unpad_empty(self):
        unpadded = unpad(b'')
        self.assertEqual(unpadded, b'')


@override_settings(SECRET_KEY='xyzzy')
class DecryptTests(SimpleTestCase):

    def test_crypto_padded(self):
        ciphertext_using_crypto_padding = 'Vh2Tmlnr5+out2PQDefkudZ2frfze5onsAlUGTLv3Oc='
        plaintext = b64_aes_decrypt(ciphertext_using_crypto_padding)
        self.assertEqual(plaintext, 'Around you is a forest.')

    def test_simple_padded(self):
        """
        Make sure we can decrypt old passwords
        """
        ciphertext_using_simple_padding = 'Vh2Tmlnr5+out2PQDefkuS9+9GtIsiEX8YBA0T/V87I='
        plaintext = b64_aes_decrypt(ciphertext_using_simple_padding)
        self.assertEqual(plaintext, 'Around you is a forest.')

    def test_known_bad_0x80(self):
        # This test documents behavior of the current implementation, and can
        # be removed when there are no encrypted passwords padded with spaces.
        password = 'a' * 14 + 'À'
        assert len(password.encode('utf-8')) == AES_BLOCK_SIZE
        ciphertext = self._encrypt_with_simple_padding(password)
        with self.assertRaises(UnicodeDecodeError):
            b64_aes_decrypt(ciphertext)

    def test_known_bad_0x00(self):
        # This test documents behavior of the current implementation, and can
        # be removed when there are no encrypted passwords padded with spaces.
        password = 'a' + 15 * '\x00'
        assert len(password.encode('utf-8')) == AES_BLOCK_SIZE
        ciphertext = self._encrypt_with_simple_padding(password)
        with self.assertRaisesRegex(ValueError, 'Padding is incorrect.'):
            b64_aes_decrypt(ciphertext)

    def test_known_bad_0x80_0x00(self):
        # This test documents behavior of the current implementation, and can
        # be removed when there are no encrypted passwords padded with spaces.
        password = 'aÀ' + 13 * '\x00'
        assert len(password.encode('utf-8')) == AES_BLOCK_SIZE
        ciphertext = self._encrypt_with_simple_padding(password)
        with self.assertRaises(UnicodeDecodeError):
            b64_aes_decrypt(ciphertext)

    def _encrypt_with_simple_padding(self, message):
        """
        Encrypts passwords the way we used to
        """
        secret_key_bytes = settings.SECRET_KEY.encode('ascii')
        aes_key = simple_pad(secret_key_bytes, AES_BLOCK_SIZE)[:AES_KEY_MAX_LEN]
        aes = AES.new(aes_key, AES.MODE_ECB)

        message_bytes = message.encode('utf8')
        plaintext_bytes = simple_pad(message_bytes, AES_BLOCK_SIZE)
        ciphertext_bytes = aes.encrypt(plaintext_bytes)
        b64ciphertext_bytes = b64encode(ciphertext_bytes)
        return b64ciphertext_bytes.decode('ascii')


class PFormatJSONTests(SimpleTestCase):

    def test_valid_json_string(self):
        self.assertEqual(
            pformat_json('{"ham": "spam", "eggs": "spam"}'),
            '{\n  "eggs": "spam",\n  "ham": "spam"\n}'
        )

    def test_dict(self):
        self.assertEqual(
            pformat_json({'ham': 'spam', 'eggs': 'spam'}),
            '{\n  "eggs": "spam",\n  "ham": "spam"\n}'
        )

    def test_valid_json_bytes(self):
        self.assertEqual(
            pformat_json(b'{"ham": "spam", "eggs": "spam"}'),
            '{\n  "eggs": "spam",\n  "ham": "spam"\n}'
        )

    def test_invalid_json_string(self):
        self.assertEqual(
            pformat_json('ham spam eggs spam'),
            'ham spam eggs spam'
        )

    def test_invalid_json_bytes(self):
        self.assertEqual(
            pformat_json(b'{"ham": "spam", "spam", "spa'),
            b'{"ham": "spam", "spam", "spa'
        )

    def test_nonascii_json_string(self):
        pigs_and_eggs = (u'{"\U0001f416": "\U0001f416\U0001f416\U0001f416", '
                         u'"\U0001f95a\U0001f95a": "\U0001f416\U0001f416\U0001f416"}')
        json_string = pformat_json(pigs_and_eggs)

        self.assertEqual(
            json_string,
            '{\n  "\\ud83d\\udc16": "\\ud83d\\udc16\\ud83d\\udc16\\ud83d\\udc16",\n  '
            '"\\ud83e\\udd5a\\ud83e\\udd5a": "\\ud83d\\udc16\\ud83d\\udc16\\ud83d\\udc16"\n}'
        )

    def test_nonascii_json_bytes(self):
        pigs_and_eggs = (u'{"\U0001f416": "\U0001f416\U0001f416\U0001f416", '
                         u'"\U0001f95a\U0001f95a": "\U0001f416\U0001f416\U0001f416"}')
        json_string = pformat_json(pigs_and_eggs.encode("utf-8"))

        self.assertEqual(
            json_string,
            '{\n  "\\ud83d\\udc16": "\\ud83d\\udc16\\ud83d\\udc16\\ud83d\\udc16",\n  '
            '"\\ud83e\\udd5a\\ud83e\\udd5a": "\\ud83d\\udc16\\ud83d\\udc16\\ud83d\\udc16"\n}'
        )

    def test_nonascii_dict(self):
        pigs_and_eggs = {"\U0001f416": "\U0001f416\U0001f416\U0001f416",
                         "\U0001f95a\U0001f95a": "\U0001f416\U0001f416\U0001f416"}
        json_string = pformat_json(pigs_and_eggs)

        self.assertEqual(
            json_string,
            '{\n  "\\ud83d\\udc16": "\\ud83d\\udc16\\ud83d\\udc16\\ud83d\\udc16",\n  '
            '"\\ud83e\\udd5a\\ud83e\\udd5a": "\\ud83d\\udc16\\ud83d\\udc16\\ud83d\\udc16"\n}'
        )
        assert json.loads(json_string) == pigs_and_eggs

    def test_empty_string(self):
        self.assertEqual(
            pformat_json(''),
            ''
        )

    def test_none(self):
        self.assertEqual(
            pformat_json(None),
            ''
        )


class EncryptionTests(SimpleTestCase):

    def assert_message_equals_plaintext_using_ecb(self, message):
        assert isinstance(message, str)
        ciphertext = b64_aes_encrypt(message)
        plaintext = b64_aes_decrypt(ciphertext)
        self.assertEqual(plaintext, message)
        self.assertIsInstance(ciphertext, str)
        self.assertIsInstance(plaintext, str)

    def test_encrypt_decrypt_ascii(self):
        message = 'Around you is a forest.'
        self.assert_message_equals_plaintext_using_ecb(message)

    def test_encrypt_decrypt_utf8(self):
        message = 'आपके आसपास एक जंगल है'
        self.assert_message_equals_plaintext_using_ecb(message)

    def assert_message_equals_plaintext_using_cbc(self, message):
        assert isinstance(message, str)
        ciphertext = b64_aes_cbc_encrypt(message)
        plaintext = b64_aes_cbc_decrypt(ciphertext)
        self.assertEqual(plaintext, message)
        self.assertIsInstance(ciphertext, str)
        self.assertIsInstance(plaintext, str)

    def test_encrypt_decrypt_cbc_ascii(self):
        message = 'Around you is a forest.'
        self.assert_message_equals_plaintext_using_cbc(message)

    def test_encrypt_decrypt_cbc_utf8(self):
        message = 'आपके आसपास एक जंगल है'
        self.assert_message_equals_plaintext_using_cbc(message)


class GetEndpointUrlTests(SimpleTestCase):

    def test_base_url_none(self):
        url = get_endpoint_url(None, 'https://example.com/foo')
        self.assertEqual(url, 'https://example.com/foo')

    def test_trailing_slash(self):
        url = get_endpoint_url('https://example.com/foo', '')
        self.assertEqual(url, 'https://example.com/foo/')

    def test_no_urls_given(self):
        with self.assertRaises(ValueError):
            get_endpoint_url(None, None)


class DocTests(SimpleTestCase):

    def test_doctests(self):
        results = doctest.testmod(corehq.motech.utils)
        self.assertEqual(results.failed, 0)
