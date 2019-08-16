# encoding: utf-8
from __future__ import absolute_import, unicode_literals

import doctest
from base64 import b64encode

from Crypto.Cipher import AES
from django.conf import settings
from django.test import SimpleTestCase, override_settings

import six

import corehq.motech.utils
from corehq.motech.utils import (
    AES_BLOCK_SIZE,
    AES_KEY_MAX_LEN,
    b64_aes_decrypt,
    b64_aes_encrypt,
    simple_pad,
    pformat_json,
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
        password = 'a' * 14 + 'À'
        assert len(password.encode('utf-8')) == AES_BLOCK_SIZE
        ciphertext = self._encrypt_with_simple_padding(password)
        with self.assertRaises(UnicodeDecodeError):
            b64_aes_decrypt(ciphertext)

    def test_known_bad_0x00(self):
        password = 'a' + 15 * '\x00'
        assert len(password.encode('utf-8')) == AES_BLOCK_SIZE
        ciphertext = self._encrypt_with_simple_padding(password)
        with self.assertRaisesRegexp(ValueError, 'Padding is incorrect.'):
            b64_aes_decrypt(ciphertext)

    def test_known_bad_0x80_0x00(self):
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
        plaintext_bytes = simple_pad(message_bytes, AES_BLOCK_SIZE)  # <-- this
        ciphertext_bytes = aes.encrypt(plaintext_bytes)
        b64ciphertext_bytes = b64encode(ciphertext_bytes)
        return b64ciphertext_bytes.decode('ascii')


class PFormatJSONTests(SimpleTestCase):

    def test_valid_json(self):
        self.assertEqual(
            pformat_json('{"ham": "spam", "eggs": "spam"}'),
            '{\n  "eggs": "spam",\n  "ham": "spam"\n}' if six.PY3 else '{\n  "eggs": "spam", \n  "ham": "spam"\n}'
        )
        self.assertEqual(
            pformat_json({'ham': 'spam', 'eggs': 'spam'}),
            '{\n  "eggs": "spam",\n  "ham": "spam"\n}' if six.PY3 else '{\n  "eggs": "spam", \n  "ham": "spam"\n}'
        )

    def test_invalid_json(self):
        self.assertEqual(
            pformat_json('ham spam eggs spam'),
            'ham spam eggs spam'
        )

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

    def assert_message_equals_plaintext(self, message):
        assert isinstance(message, six.text_type)
        ciphertext = b64_aes_encrypt(message)
        plaintext = b64_aes_decrypt(ciphertext)
        self.assertEqual(plaintext, message)
        self.assertIsInstance(ciphertext, six.text_type)
        self.assertIsInstance(plaintext, six.text_type)

    def test_encrypt_decrypt_ascii(self):
        message = 'Around you is a forest.'
        self.assert_message_equals_plaintext(message)

    def test_encrypt_decrypt_utf8(self):
        message = 'आपके आसपास एक जंगल है'
        self.assert_message_equals_plaintext(message)


class DocTests(SimpleTestCase):

    def test_doctests(self):
        results = doctest.testmod(corehq.motech.utils)
        self.assertEqual(results.failed, 0)
