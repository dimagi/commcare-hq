import json
from base64 import b64decode, b64encode
from typing import Optional, Sequence

from django.conf import settings

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad as crypto_pad
from Crypto.Util.Padding import unpad as crypto_unpad
from Crypto.Util.py3compat import bord
from Crypto.Random import get_random_bytes

from corehq.motech.const import AUTH_PRESETS, OAUTH2_PWD, ALGO_AES_CBC, ALGO_AES

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


def b64_aes_cbc_encrypt(message):
    """
    AES-encrypt and base64-encode `message` using CBC mode.

    Uses Django SECRET_KEY as AES key and generates a random IV.
    """
    if isinstance(settings.SECRET_KEY, bytes):
        secret_key_bytes = settings.SECRET_KEY
    else:
        secret_key_bytes = settings.SECRET_KEY.encode('ascii')
    aes_key = simple_pad(secret_key_bytes, AES_BLOCK_SIZE)[:AES_KEY_MAX_LEN]
    # We never need to unpad the key, so simple_pad() is fine (and
    # allows us to decrypt old values).
    iv = get_random_bytes(AES_BLOCK_SIZE)
    aes = AES.new(aes_key, AES.MODE_CBC, iv)

    message_bytes = message if isinstance(message, bytes) else message.encode('utf8')
    plaintext_bytes = crypto_pad(message_bytes, AES_BLOCK_SIZE, style='iso7816')
    ciphertext_bytes = aes.encrypt(plaintext_bytes)

    b64ciphertext_bytes = b64encode(iv + ciphertext_bytes)
    return b64ciphertext_bytes.decode('ascii')


def b64_aes_cbc_decrypt(message):
    """
    Base64-decode and AES-decrypt ASCII `message` using CBC mode.

    Uses Django SECRET_KEY as AES key.

    >>> settings.SECRET_KEY = 'xyzzy'
    >>> b64_aes_cbc_decrypt('6WbQuezOKqp4AMOCoUOndVnAUDL13e0fl3cpxcgHX/AlcPwN4+poaetdjwgikz0F')
    'Around you is a forest.'
    """
    if isinstance(settings.SECRET_KEY, bytes):
        secret_key_bytes = settings.SECRET_KEY
    else:
        secret_key_bytes = settings.SECRET_KEY.encode('ascii')
    aes_key = simple_pad(secret_key_bytes, AES_BLOCK_SIZE)[:AES_KEY_MAX_LEN]

    decoded_bytes = b64decode(message)
    iv = decoded_bytes[:AES_BLOCK_SIZE]
    ciphertext_bytes = decoded_bytes[AES_BLOCK_SIZE:]

    aes = AES.new(aes_key, AES.MODE_CBC, iv)
    padded_plaintext_bytes = aes.decrypt(ciphertext_bytes)
    plaintext_bytes = unpad(padded_plaintext_bytes)
    return plaintext_bytes.decode('utf8')


# Only needed for migration from ECB to CBC mode.
def reencrypt_ecb_to_cbc_mode(encrypted_text, existing_prefix=None):
    """
    Re-encrypt a message that was encrypted using ECB mode to CBC mode.
    """
    if not encrypted_text:
        return encrypted_text

    if existing_prefix and encrypted_text.startswith(existing_prefix):
        ciphertext = encrypted_text[len(existing_prefix):]
    else:
        ciphertext = encrypted_text

    new_ciphertext = b64_aes_cbc_encrypt(b64_aes_decrypt(ciphertext))
    return f'${ALGO_AES_CBC}${new_ciphertext}'


# Only needed for migration revert from CBC to ECB mode.
def reencrypt_cbc_to_ecb_mode(encrypted_text, existing_prefix=None):
    """
    Re-encrypt a message that was encrypted using CBC mode to ECB mode.
    """
    if not encrypted_text:
        return encrypted_text

    if existing_prefix and encrypted_text.startswith(existing_prefix):
        ciphertext = encrypted_text[len(existing_prefix):]
    else:
        ciphertext = encrypted_text

    new_ciphertext = b64_aes_encrypt(b64_aes_cbc_decrypt(ciphertext))
    return f'${ALGO_AES}${new_ciphertext}'


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
    if bytestring == b'':
        return bytestring
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


def get_endpoint_url(
    base_url: Optional[str],
    endpoint: Optional[str],
) -> str:
    """
    Joins ``endpoint`` to ``base_url``. If either are None, returns the
    other. If both are None, raises ValueError.

    >>> get_endpoint_url('https://example.com/', '/foo')
    'https://example.com/foo'

    >>> get_endpoint_url('https://example.com', 'foo')
    'https://example.com/foo'

    >>> get_endpoint_url('https://example.com/foo', None)
    'https://example.com/foo'

    """
    if base_url is None and endpoint is None:
        raise ValueError('No URLs given')
    if base_url is None:
        return endpoint
    if endpoint is None:
        return base_url
    return '/'.join((base_url.rstrip('/'), endpoint.lstrip('/')))


def simplify_list(seq: Sequence):
    """
    Reduces ``seq`` to its only element, or ``None`` if it is empty.

    >>> simplify_list([1])
    1
    >>> simplify_list([1, 2, 3])
    [1, 2, 3]
    >>> type(simplify_list([]))
    <class 'NoneType'>

    """
    if len(seq) == 1:
        return seq[0]
    if not seq:
        return None
    return seq


def copy_api_auth_settings(connection):
    if connection.auth_type != OAUTH2_PWD:
        return

    api_settings = AUTH_PRESETS[connection.api_auth_settings]

    connection.token_url = get_endpoint_url(connection.url, api_settings.token_endpoint)
    connection.refresh_url = get_endpoint_url(connection.url, api_settings.refresh_endpoint)
    connection.pass_credentials_in_header = api_settings.pass_credentials_in_header

    connection.save()


def api_setting_matches_preset(connection):
    def split_url(url):
        if not url:
            return None
        try:
            return url.split(connection.url.rstrip('/'))[1]
        except IndexError:
            return None
    for preset_slug, preset in AUTH_PRESETS.items():
        if (
            split_url(connection.token_url) == preset.token_endpoint
            and split_url(connection.refresh_url) == preset.refresh_endpoint
            and connection.pass_credentials_in_header == preset.pass_credentials_in_header
        ):
            return preset_slug

    if connection.token_url is not None or connection.refresh_url is not None:
        return 'CUSTOM'

    return None
