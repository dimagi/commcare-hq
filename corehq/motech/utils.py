from __future__ import absolute_import
from __future__ import unicode_literals

import json
from base64 import b64decode, b64encode

import six
from Crypto.Cipher import AES
from django.conf import settings


AES_BLOCK_SIZE = 16
AES_KEY_MAX_LEN = 32  # AES key must be either 16, 24, or 32 bytes long
PAD_CHAR = b' '


def pad(bytestring, block_size, char=PAD_CHAR):
    """
    Pad `bytestring` to a multiple of `block_size` in length by appending
    `char`. `char` defaults to space.

    >>> padded = pad(b'xyzzy', 8, b'*')
    >>> padded == b'xyzzy***'
    True

    """
    assert isinstance(bytestring, bytes)
    padding = ((block_size - len(bytestring)) % block_size) * char
    return bytestring + padding


def b64_aes_encrypt(message):
    """
    AES-encrypt and base64-encode `message`.

    Uses Django SECRET_KEY as AES key.

    >>> settings.SECRET_KEY = 'xyzzy'
    >>> encrypted = b64_aes_encrypt('Around you is a forest.')
    >>> encrypted == 'Vh2Tmlnr5+out2PQDefkuS9+9GtIsiEX8YBA0T/V87I='
    True

    """
    key = settings.SECRET_KEY if isinstance(settings.SECRET_KEY, bytes) else settings.SECRET_KEY.encode('ascii')
    secret = pad(key, AES_BLOCK_SIZE)[:AES_KEY_MAX_LEN]
    aes = AES.new(secret, AES.MODE_ECB)

    message_bytes = message if isinstance(message, bytes) else message.encode('utf8')
    plaintext = pad(message_bytes, AES_BLOCK_SIZE)
    ciphertext = aes.encrypt(plaintext)
    return b64encode(ciphertext)


def b64_aes_decrypt(message):
    """
    Base64-decode and AES-decrypt ASCII `message`.

    Uses Django SECRET_KEY as AES key.

    >>> settings.SECRET_KEY = 'xyzzy'
    >>> decrypted = b64_aes_decrypt(b'Vh2Tmlnr5+out2PQDefkuS9+9GtIsiEX8YBA0T/V87I=')
    >>> decrypted == 'Around you is a forest.'
    True

    """
    key = settings.SECRET_KEY if isinstance(settings.SECRET_KEY, bytes) else settings.SECRET_KEY.encode('ascii')
    secret = pad(key, AES_BLOCK_SIZE)[:AES_KEY_MAX_LEN]
    aes = AES.new(secret, AES.MODE_ECB)

    ciphertext = b64decode(message)
    plaintext = aes.decrypt(ciphertext)
    return plaintext.rstrip(PAD_CHAR)


def pformat_json(data):
    """
    Pretty-formats `data` for readability, or returns the original
    value if it can't be parsed as JSON.

    :return: A 2-space-indented string with sorted keys.

    >>> print(pformat_json('{"ham": "spam", "eggs": "spam"}'))
    {
      "eggs": "spam", 
      "ham": "spam"
    }
    >>> print(pformat_json({'ham': 'spam', 'eggs': 'spam'}))
    {
      "eggs": "spam", 
      "ham": "spam"
    }
    >>> print(pformat_json('ham spam eggs spam'))
    ham spam eggs spam

    """
    try:
        json_data = json.loads(data) if isinstance(data, six.string_types) else data
        return json.dumps(json_data, indent=2, sort_keys=True)
    except ValueError:
        return data
