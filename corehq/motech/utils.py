# encoding: utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import json
from base64 import b64decode, b64encode

import six
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad as crypto_pad, unpad as crypto_unpad
from Crypto.Util.py3compat import bord
from django.conf import settings

from corehq.util.python_compatibility import soft_assert_type_text

AES_BLOCK_SIZE = 16
AES_KEY_MAX_LEN = 32  # AES key must be either 16, 24, or 32 bytes long
PAD_CHAR = b' '


def simple_pad(bytestring, block_size, char=PAD_CHAR):
    """
    Pad `bytestring` to a multiple of `block_size` in length by appending
    `char`. `char` defaults to space.

    >>> padded = simple_pad(b'xyzzy', 8, b'*')
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
    >>> encrypted == 'Vh2Tmlnr5+out2PQDefkudZ2frfze5onsAlUGTLv3Oc='
    True

    """
    if isinstance(settings.SECRET_KEY, bytes):
        secret_key_bytes = settings.SECRET_KEY
    else:
        secret_key_bytes = settings.SECRET_KEY.encode('ascii')
    aes_key = simple_pad(secret_key_bytes, AES_BLOCK_SIZE)[:AES_KEY_MAX_LEN]
    # We never need to unpad the key, so simple_pad() is fine (and
    # allows us to decrypt old values).
    aes = AES.new(aes_key, AES.MODE_ECB)

    message_bytes = message if isinstance(message, bytes) else message.encode('utf8')
    plaintext_bytes = crypto_pad(message_bytes, AES_BLOCK_SIZE, style='iso7816')
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
    aes_key = simple_pad(secret_key_bytes, AES_BLOCK_SIZE)[:AES_KEY_MAX_LEN]
    aes = AES.new(aes_key, AES.MODE_ECB)

    ciphertext_bytes = b64decode(message)
    padded_plaintext_bytes = aes.decrypt(ciphertext_bytes)
    plaintext_bytes = unpad(padded_plaintext_bytes)
    return plaintext_bytes.decode('utf8')


def unpad(bytestring):
    """
    Unpad will remove padding from the right of a string that has been
    padded by ``simple_pad()`` or by ``crypto_pad()``.

    ``crypto_pad()`` uses `ISO 7816-4 <iso7816>`_, which will result in
    the string ending in a byte with a decimal value of either 0 or 128
    (hex 0x00 or 0x80).

     ``simple_pad()`` pads with PAD_CHAR (an ASCII space character) if
     the original length is not a multiple of AES_BLOCK_SIZE, otherwise
     it does not pad.

     If ``bytestring`` ends in 0x00 or 0x80, it could have been padded
     with ``crypto_pad()``, or it could padded with ``simple_pad()``
     and whose last character is multi-byte non-ASCII UTF-8 character
     whose last byte is 0x00 or 0x80 (e.g. b'0xC3\0x80', "À" (capital
     A-grave)). Because the second possibility is far less likely than
     the first, ``unpad()`` uses ``crypto_unpad()`` in this case.

    .. _iso7816: https://en.wikipedia.org/wiki/Padding_(cryptography)#ISO/IEC_7816-4
    """
    if bord(bytestring[-1]) in (0, 128):
        return crypto_unpad(bytestring, AES_BLOCK_SIZE, style='iso7816')
    return bytestring.rstrip(PAD_CHAR)


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
