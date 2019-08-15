from __future__ import absolute_import
from __future__ import unicode_literals

import json
from base64 import b64decode, b64encode

import six
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from django.conf import settings

from corehq.util.python_compatibility import soft_assert_type_text

AES_BLOCK_SIZE = 16
AES_KEY_MAX_LEN = 32  # AES key must be either 16, 24, or 32 bytes long


def b64_aes_encrypt(message):
    """
    AES-encrypt and base64-encode `message`.

    Uses Django SECRET_KEY as AES key.

    >>> settings.SECRET_KEY = 'xyzzy'
    >>> encrypted = b64_aes_encrypt('Around you is a forest.')
    >>> encrypted == 'Vh2Tmlnr5+out2PQDefkuS9+9GtIsiEX8YBA0T/V87I='
    True

    """
    if isinstance(settings.SECRET_KEY, bytes):
        secret_key_bytes = settings.SECRET_KEY
    else:
        secret_key_bytes = settings.SECRET_KEY.encode('ascii')
    aes_key = pad(secret_key_bytes, AES_BLOCK_SIZE)[:AES_KEY_MAX_LEN]
    aes = AES.new(aes_key, AES.MODE_ECB)

    message_bytes = message if isinstance(message, bytes) else message.encode('utf8')
    plaintext_bytes = pad(message_bytes, AES_BLOCK_SIZE)
    ciphertext_bytes = aes.encrypt(plaintext_bytes)
    b64ciphertext_bytes = b64encode(ciphertext_bytes)
    return b64ciphertext_bytes.decode('ascii')


def b64_aes_decrypt(message):
    """
    Base64-decode and AES-decrypt ASCII `message`.

    Uses Django SECRET_KEY as AES key.

    >>> settings.SECRET_KEY = 'xyzzy'
    >>> decrypted = b64_aes_decrypt('Vh2Tmlnr5+out2PQDefkuS9+9GtIsiEX8YBA0T/V87I=')
    >>> decrypted == 'Around you is a forest.'
    True

    """
    if isinstance(settings.SECRET_KEY, bytes):
        secret_key_bytes = settings.SECRET_KEY
    else:
        secret_key_bytes = settings.SECRET_KEY.encode('ascii')
    aes_key = pad(secret_key_bytes, AES_BLOCK_SIZE)[:AES_KEY_MAX_LEN]
    aes = AES.new(aes_key, AES.MODE_ECB)

    ciphertext_bytes = b64decode(message)
    padded_plaintext_bytes = aes.decrypt(ciphertext_bytes)
    plaintext_bytes = unpad(padded_plaintext_bytes, AES_BLOCK_SIZE)
    return plaintext_bytes.decode('utf8')


def pformat_json(data):
    """
    Pretty-formats `data` for readability, or returns the original
    value if it can't be parsed as JSON.

    :return: A 2-space-indented string with sorted keys.
    """
    if data is None:
        return ''
    try:
        if isinstance(data, six.string_types):
            soft_assert_type_text(data)
        json_data = json.loads(data) if isinstance(data, six.string_types) else data
        return json.dumps(json_data, indent=2, sort_keys=True)
    except ValueError:
        return data
