import re
from tastypie.authentication import ApiKeyAuthentication


J2ME = 'j2me'
ANDROID = 'android'


def determine_authtype_from_header(request, default=None):
    """
    Guess the auth type, based on the headers found in the request.
    """
    auth_header = (request.META.get('HTTP_AUTHORIZATION') or '').lower()
    if auth_header.startswith('basic '):
        return 'basic'
    elif auth_header.startswith('digest '):
        return 'digest'
    elif all(ApiKeyAuthentication().extract_credentials(request)):
        return 'api_key'

    return default


def determine_authtype_from_request(request, default='basic'):
    """
    Guess the auth type, based on the (phone's) user agent or the
    headers found in the request.
    """
    user_agent = request.META.get('HTTP_USER_AGENT')
    type_to_auth_map = {
        J2ME: 'digest',
        ANDROID: 'basic',
    }
    user_type = guess_phone_type_from_user_agent(user_agent)
    if user_type is not None:
        return type_to_auth_map.get(user_type, default)
    else:
        return determine_authtype_from_header(request, default=default)


def guess_phone_type_from_user_agent(user_agent):
    """
    A really dumb utility that guesses the phone type based on the user-agent header.
    """
    j2me_pattern = '[Nn]okia|NOKIA|CLDC|cldc|MIDP|midp|Series60|Series40|[Ss]ymbian|SymbOS|[Mm]aemo'
    if user_agent:
        if re.search(j2me_pattern, user_agent):
            return J2ME
        elif 'Android' in user_agent:
            return ANDROID
    return None
