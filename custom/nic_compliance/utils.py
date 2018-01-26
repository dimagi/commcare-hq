from __future__ import absolute_import
import re
import base64
from datetime import timedelta
from django.conf import settings

from django.contrib.auth.hashers import SHA1PasswordHasher

from dimagi.utils.couch.cache.cache_core import get_redis_client

from corehq.util.view_utils import get_request
from custom.nic_compliance.const import EXPIRE_LOGIN_ATTEMPTS_IN, REDIS_LOGIN_ATTEMPTS_LIST_PREFIX

# Use SHA1PasswordHasher instead of default CustomSHA256PasswordHasher when set, since it
# can't be used due to it's custom behaviour
PASSWORD_HASHER = SHA1PasswordHasher()
# Passwords set with expected padding length and format would respect this regex
PASSWORD_REGEX = r"^sha256\$([a-z0-9A-Z]{6})(\S*)([a-z0-9A-Z]{6})=$"
PASSWORD_REGEX_COMPILER = re.compile(PASSWORD_REGEX)


def extract_password(obfuscated_password):
    # match regex for padding along with inner block and find matches
    match_result = PASSWORD_REGEX_COMPILER.match(obfuscated_password)
    # ensure regex match for obfuscated password and three matches
    if match_result and len(match_result.groups()) == 3:
        match_groups = match_result.groups()
        padding_left, encoded_internal_block, padding_right = match_groups
        # b64 decode the encoded internal block to get raw internal block
        # raw internal block = (paddling_left + encoded_password + padding_right)
        try:
            decoded_internal_block = base64.b64decode(encoded_internal_block)
        except TypeError:
            return ''
        # match regex for padding along with b64 encoded password and find matches
        match_result_2 = PASSWORD_REGEX_COMPILER.match(decoded_internal_block)
        # ensure regex match for the internal block and 3 matches
        if match_result_2 and len(match_result_2.groups()) == 3:
            match_groups = match_result_2.groups()
            # ensure the same padding was used in the internal block as the outer
            if match_groups[0] == padding_left and match_groups[2] == padding_right:
                b64_encoded_password = match_groups[1]
                try:
                    # decode to get the b64encoded real password
                    # return password decoded for UTF-8 support
                    return base64.b64decode(b64_encoded_password).decode('utf-8')
                except TypeError:
                    return ''
            else:
                # this sounds like someone tried to obfuscate password but failed so ignore the password submitted
                # completely
                return ''
        else:
            # this sounds like someone tried to obfuscate password but failed so ignore the password submitted
            # completely
            return ''
    else:
        # return the password received AS-IS
        return obfuscated_password


def hash_password(password):
    return PASSWORD_HASHER.encode(password, PASSWORD_HASHER.salt())


def verify_password(password, encoded_password):
    return PASSWORD_HASHER.verify(password, encoded_password)


def obfuscated_passwords_redis_key_for_user(username):
    return REDIS_LOGIN_ATTEMPTS_LIST_PREFIX + username


def get_obfuscated_passwords(username):
    client = get_redis_client()
    return client.get(obfuscated_passwords_redis_key_for_user(username), [])


def get_raw_password(obfuscated_password, username=None):
    def replay_attack():
        # Replay attack where the same obfuscated password used from previous login attempt
        obfuscated_passwords = get_obfuscated_passwords(username)
        for submitted_obfuscated_password in obfuscated_passwords:
            if verify_password(obfuscated_password, submitted_obfuscated_password):
                return True

    def record_login_attempt():
        client = get_redis_client()
        key_name = obfuscated_passwords_redis_key_for_user(username)
        obfuscated_passwords = client.get(key_name, [])
        client.set(key_name, obfuscated_passwords + [hash_password(obfuscated_password)])
        client.expire(key_name, timedelta(EXPIRE_LOGIN_ATTEMPTS_IN))

    def _decode_password():
        # force check for replay attack and recording login attempt only for web sign in by checking for username
        # Also skip those two checks in case of 2-step authentication by checking for auth-username which is not
        # present in consecutive token step's POST params
        if username and request and request.POST.get('auth-username'):
            if replay_attack():
                return ''
            record_login_attempt()
        return extract_password(obfuscated_password)

    if settings.OBFUSCATE_PASSWORD_FOR_NIC_COMPLIANCE:
        request = get_request()
        if request:
            # 1. an attempt to decode a password should be done just once in a request for the login attempt
            # check to work correctly and not consider it a replay attack in case of multiple calls
            # 2. also there should be no need to decode a password multiple times in the same request.
            if not hasattr(request, 'decoded_password'):
                request.decoded_password = {}

            # return decoded password set on request object for the obfuscated_password
            if obfuscated_password in request.decoded_password:
                return request.decoded_password[obfuscated_password]
            else:
                # decode the password and save it on the request object for obfuscated_password
                request.decoded_password[obfuscated_password] = _decode_password()
                return request.decoded_password[obfuscated_password]
        else:
            return _decode_password()
    else:
        return obfuscated_password
