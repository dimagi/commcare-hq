import base64
import re
from django.contrib.auth import authenticate
from django.http import HttpResponse
from tastypie.authentication import ApiKeyAuthentication


J2ME = 'j2me'
ANDROID = 'android'

BASIC = 'basic'
DIGEST = 'digest'
API_KEY = 'api_key'


def determine_authtype_from_header(request, default=None):
    """
    Guess the auth type, based on the headers found in the request.
    """
    auth_header = (request.META.get('HTTP_AUTHORIZATION') or '').lower()
    if auth_header.startswith('basic '):
        return BASIC
    elif auth_header.startswith('digest '):
        return DIGEST
    elif all(ApiKeyAuthentication().extract_credentials(request)):
        return API_KEY

    return default


def determine_authtype_from_request(request, default='basic'):
    """
    Guess the auth type, based on the (phone's) user agent or the
    headers found in the request.
    """
    user_agent = request.META.get('HTTP_USER_AGENT')
    type_to_auth_map = {
        J2ME: DIGEST,
        ANDROID: BASIC,
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


def basicauth(realm=''):
    # stolen and modified from: https://djangosnippets.org/snippets/243/
    def real_decorator(view):
        def wrapper(request, *args, **kwargs):
            if 'HTTP_AUTHORIZATION' in request.META:
                auth = request.META['HTTP_AUTHORIZATION'].split()
                if len(auth) == 2:
                    if auth[0].lower() == BASIC:
                        uname, passwd = base64.b64decode(auth[1]).split(':', 1)
                        user = authenticate(username=uname, password=passwd)
                        if user is not None and user.is_active:
                            request.user = user
                            return view(request, *args, **kwargs)

            # Either they did not provide an authorization header or
            # something in the authorization attempt failed. Send a 401
            # back to them to ask them to authenticate.
            response = HttpResponse(status=401)
            response['WWW-Authenticate'] = 'Basic realm="%s"' % realm
            return response
        return wrapper
    return real_decorator
