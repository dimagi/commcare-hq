from __future__ import absolute_import

from __future__ import unicode_literals
import json
from base64 import b64decode, b64encode

import six
from Crypto.Cipher import AES
from django.conf import settings


AES_BLOCK_SIZE = 16
AES_KEY_MAX_LEN = 32  # AES key must be either 16, 24, or 32 bytes long
PAD_CHAR = ' '


def pad(string, block_size, char=PAD_CHAR):
    """
    Pad `string` to a multiple of `block_size` in length by appending
    `char`. `char` defaults to space.

    >>> pad('xyzzy', 8)
    'xyzzy   '

    """
    padding = ((block_size - len(string)) % block_size) * char
    return string + padding


def b64_aes_encrypt(message):
    """
    AES-encrypt and base64-encode `message`.

    Uses Django SECRET_KEY as AES key.

    >>> settings.SECRET_KEY = 'xyzzy'
    >>> b64_aes_encrypt('Around you is a forest.')
    'Vh2Tmlnr5+out2PQDefkuS9+9GtIsiEX8YBA0T/V87I='

    """
    secret = pad(settings.SECRET_KEY, AES_BLOCK_SIZE)[:AES_KEY_MAX_LEN]
    aes = AES.new(secret)

    plaintext = pad(message, AES_BLOCK_SIZE)
    ciphertext = aes.encrypt(plaintext)
    return b64encode(ciphertext)


def b64_aes_decrypt(message):
    """
    Base64-decode and AES-decrypt `message`.

    Uses Django SECRET_KEY as AES key.

    >>> settings.SECRET_KEY = 'xyzzy'
    >>> b64_aes_decrypt('Vh2Tmlnr5+out2PQDefkuS9+9GtIsiEX8YBA0T/V87I=')
    'Around you is a forest.'

    """
    secret = pad(settings.SECRET_KEY, AES_BLOCK_SIZE)[:AES_KEY_MAX_LEN]
    aes = AES.new(secret)

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
