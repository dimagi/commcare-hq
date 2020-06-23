import json
from base64 import b64decode, b64encode
from typing import Optional

from django.conf import settings

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad as crypto_pad
from Crypto.Util.Padding import unpad as crypto_unpad
from Crypto.Util.py3compat import bord

AES_BLOCK_SIZE = 16
AES_KEY_MAX_LEN = 32  # AES key must be either 16, 24, or 32 bytes long
PAD_CHAR = b' '


def simple_pad(bytestring, block_size, char=PAD_CHAR):
    """
    Pad `bytestring` to a multiple of `block_size` in length by appending
    `char`. `char` defaults to space.

    >>> simple_pad(b'xyzzy', 8, b'*')
    b'xyzzy***'

    """
    assert isinstance(bytestring, bytes)
    padding = ((block_size - len(bytestring)) % block_size) * char
    return bytestring + padding


def b64_aes_encrypt(message):
    """
    AES-encrypt and base64-encode `message`.

    Uses Django SECRET_KEY as AES key.

    >>> settings.SECRET_KEY = 'xyzzy'
    >>> b64_aes_encrypt('Around you is a forest.')
    'Vh2Tmlnr5+out2PQDefkudZ2frfze5onsAlUGTLv3Oc='

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
    >>> b64_aes_decrypt('Vh2Tmlnr5+out2PQDefkuS9+9GtIsiEX8YBA0T/V87I=')
    'Around you is a forest.'

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
        json_data = json.loads(data) if isinstance(data, (str, bytes)) else data
        return json.dumps(json_data, indent=2, sort_keys=True)
    except (TypeError, ValueError):
        return data


def unpack_request_args(request_method, args, kwargs):
    params = kwargs.pop('params', None)
    json_data = kwargs.pop('json', None)  # dict
    data = kwargs.pop('data', None)  # string
    if data is None:
        data = json_data
    # Don't bother trying to cast `data` as a dict.
    # RequestLog.request_body will store it, and it will be rendered
    # as prettified JSON if possible, regardless of whether it's a
    # dict or a string.
    if args:
        if request_method == 'GET':
            params = args[0]
        elif request_method == 'PUT':
            data = args[0]
    headers = kwargs.pop('headers', {})
    return params, data, headers


def get_endpoint_url(base_url: Optional[str], endpoint: str) -> str:
    """
    Joins ``endpoint`` to ``base_url`` if ``base_url`` is not None.

    >>> get_endpoint_url('https://example.com/', '/foo')
    'https://example.com/foo'

    >>> get_endpoint_url('https://example.com', 'foo')
    'https://example.com/foo'

    >>> get_endpoint_url(None, 'https://example.com/foo')
    'https://example.com/foo'

    """
    if base_url is None:
        return endpoint
    return '/'.join((base_url.rstrip('/'), endpoint.lstrip('/')))
