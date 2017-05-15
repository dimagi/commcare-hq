import re
import base64
from datetime import timedelta
from django.conf import settings

from django.contrib.auth.hashers import get_hasher

from dimagi.utils.couch.cache.cache_core import get_redis_client

from corehq.util.view_utils import get_request
from custom.nic_compliance.const import EXPIRE_LOGIN_ATTEMPTS_IN, REDIS_LOGIN_ATTEMPTS_LIST_PREFIX

PASSWORD_HASHER = get_hasher()


def extract_password(password):
    # Passwords set with expected salts length and padding would respect this regex
    reg_exp = r"^sha256\$([a-z0-9A-Z]{6})([a-zA-Z0-9=]*)([a-z0-9A-Z]{6})=$"
    match_result = re.match(reg_exp, password)
    # strip out outer level padding of salts/keys and ensure three matches
    if match_result and len(match_result.groups()) == 3:
        match_groups = match_result.groups()
        hash_left, stripped_password, hash_right = match_groups
        # decode the stripped password to get internal block
        # decoded(salt1 + encoded_password + salt2)
        try:
            decoded_password = base64.b64decode(stripped_password)
        except TypeError:
            return ''
        match_result_2 = re.match(reg_exp, decoded_password)
        # strip out hashes from the internal block and ensure 3 matches
        if match_result_2 and len(match_result_2.groups()) == 3:
            match_groups = match_result_2.groups()
            # ensure the same hashes were used in the internal block as the outer
            if match_groups[0] == hash_left and match_groups[2] == hash_right:
                # decode to get the real password
                password_hash = match_groups[1]
                # return password decoded for UTF-8 support
                try:
                    return base64.b64decode(password_hash).decode('utf-8')
                except TypeError:
                    return ''
            else:
                # this sounds like someone tried to hash something but failed so ignore the password submitted
                # completely
                return ''
        else:
            # this sounds like someone tried to hash something but failed so ignore the password submitted
            # completely
            return ''
    else:
        # return the password received AS-IS
        return password


def hash_password(password):
    return PASSWORD_HASHER.encode(password, PASSWORD_HASHER.salt())


def verify_password(password, password_salt):
    return PASSWORD_HASHER.verify(password, password_salt)


def login_attempts_redis_key_for_user(username):
    return REDIS_LOGIN_ATTEMPTS_LIST_PREFIX + username


def get_login_attempts(username):
    client = get_redis_client()
    return client.get(login_attempts_redis_key_for_user(username), [])


def get_decoded_password(password_hash, username=None):
    def replay_attack():
        # Replay attack where the same hash used from previous login attempt
        login_attempts = get_login_attempts(username)
        for login_attempt in login_attempts:
            if verify_password(password_hash, login_attempt):
                return True

    def record_login_attempt():
        client = get_redis_client()
        login_attempts = client.get(login_attempts_redis_key_for_user(username), [])
        key_name = login_attempts_redis_key_for_user(username)
        client.set(key_name, login_attempts + [hash_password(password_hash)])
        client.expire(key_name, timedelta(EXPIRE_LOGIN_ATTEMPTS_IN))

    def _decode_password():
        # force check for replay attack and recording login attempt only for web sign in by checking for username
        # Also skip those two checks in case of 2-step authentication by checking for auth-username which is not
        # present in consecutive token step's POST params
        if username and request and request.POST.get('auth-username'):
            if replay_attack():
                return ''
            record_login_attempt()
        return extract_password(password_hash)

    if settings.ENABLE_PASSWORD_HASHING:
        request = get_request()
        if request:
            # 1. an attempt to decode a password should be done just once in a request for the login attempt
            # check to work correctly and not consider it a replay attack in case of multiple calls
            # 2. also there should be no need to decode a password multiple times in the same request.
            if not hasattr(request, 'decoded_password'):
                request.decoded_password = {}

            # return decoded password set on request object for the password_hash
            if request.decoded_password.get(password_hash):
                return request.decoded_password[password_hash]
            else:
                # decode the password and save it on the request object for password_hash
                request.decoded_password[password_hash] = _decode_password()
                return request.decoded_password[password_hash]
        else:
            return _decode_password()
    else:
        return password_hash
