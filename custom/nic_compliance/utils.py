import re
import base64
import hashlib
from datetime import timedelta
from django.conf import settings
from django.urls import resolve

from django.contrib.auth.hashers import get_hasher

from dimagi.utils.couch.cache.cache_core import get_redis_client

from corehq.util.view_utils import get_request
from custom.nic_compliance.const import (
    EXPIRE_LOGIN_ATTEMPTS_IN,
    REDIS_LOGIN_ATTEMPTS_LIST_PREFIX,
    MOBILE_REQUESTS_TO_TRACK_FOR_REPLAY_ATTACK,
    USERS_TO_TRACK_FOR_REPLAY_ATTACK,
)

PASSWORD_HASHER = get_hasher()
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
            decoded_internal_block = base64.b64decode(encoded_internal_block).decode('utf-8')
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
        return None


def hash_password(password):
    return PASSWORD_HASHER.encode(password, PASSWORD_HASHER.salt())


def verify_password(password, encoded_password):
    return PASSWORD_HASHER.verify(password, encoded_password)


def obfuscated_password_redis_key_for_user(username, obfuscated_password):
    return REDIS_LOGIN_ATTEMPTS_LIST_PREFIX + hashlib.md5(
        ("%s%s" % (username, obfuscated_password)).encode('utf-8')
    ).hexdigest()


def get_raw_password(obfuscated_password, username=None):
    client = get_redis_client()

    def replay_attack():
        # Replay attack where the same obfuscated password used from previous login attempt
        key_name = obfuscated_password_redis_key_for_user(username, obfuscated_password)
        if client.get(key_name):
            return True

    def record_login_attempt():
        key_name = obfuscated_password_redis_key_for_user(username, obfuscated_password)
        client.set(key_name, True)
        client.expire(key_name, timedelta(days=EXPIRE_LOGIN_ATTEMPTS_IN))

    def _mobile_request_to_track(username):
        # To be added just for audit test and should be removed to implement for all users
        if username not in USERS_TO_TRACK_FOR_REPLAY_ATTACK:
            return False
        return resolve(request.path).url_name in MOBILE_REQUESTS_TO_TRACK_FOR_REPLAY_ATTACK

    def _decode_password():
        raw_password = extract_password(obfuscated_password)
        if raw_password is None:
            # if there was no obfuscation done, just return the raw password
            # and skip any further checks
            return obfuscated_password
        # In case of 2-step authentication for web skip by checking for auth-username which is
        # present in first step
        if username and (
                (request and request.POST.get('auth-username')) or
                _mobile_request_to_track(username)):
            if replay_attack():
                return ''
            record_login_attempt()
        return raw_password

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
