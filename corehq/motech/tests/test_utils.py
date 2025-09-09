import doctest
import json

from django.test import SimpleTestCase, override_settings

import corehq.motech.utils
from corehq.motech.utils import (
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
        ciphertext_using_crypto_padding = 'RkmfhFuw5pudnb2eq1O8Rxu4MQjngXH307Nu0BtW3Ih/9dXOl1QE1p5F4aseK5iI'
        plaintext = b64_aes_cbc_decrypt(ciphertext_using_crypto_padding)
        self.assertEqual(plaintext, 'Around you is a forest.')


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
