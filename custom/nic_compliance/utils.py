import re
import base64
from django.conf import settings

from django.contrib.auth.hashers import get_hasher

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


def get_raw_password(obfuscated_password):
    def _decode_password():
        raw_password = extract_password(obfuscated_password)
        if raw_password is None:
            # if there was no obfuscation done, just return the raw password
            return obfuscated_password
        return raw_password

    if settings.OBFUSCATE_PASSWORD_FOR_NIC_COMPLIANCE:
        return _decode_password()
    else:
        return obfuscated_password
