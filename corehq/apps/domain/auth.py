from __future__ import absolute_import
import base64
import re
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed
from functools import wraps
from django.contrib.auth import authenticate
from django.http import HttpResponse
from tastypie.authentication import ApiKeyAuthentication
from corehq.toggles import ANONYMOUS_WEB_APPS_USAGE
from python_digest import parse_digest_credentials

J2ME = 'j2me'
ANDROID = 'android'

BASIC = 'basic'
DIGEST = 'digest'
API_KEY = 'api_key'
TOKEN = 'token'


def determine_authtype_from_header(request, default=DIGEST):
    """
    Guess the auth type, based on the headers found in the request.

    If default is set to something other than DIGEST, digest auth will not work

    CommCare mobile sends an unauthenticated request first, and we need to
    issue a basic auth challenge in response. This means we can't support both
    CommCare mobile and digest auth at the same endpoint (since digest auth
    requires a digest auth challenge).

    For non-mobile endpoints (such as APIs), we can support basic, digest,
    token, and apikey by defaulting to digest, since in all other cases, the
    client should send the initial request with an Authorization header.
    """
    auth_header = (request.META.get('HTTP_AUTHORIZATION') or '').lower()
    if auth_header.startswith('basic '):
        return BASIC
    elif auth_header.startswith('digest '):
        # Note: this will not identify initial, uncredentialed digest requests
        return DIGEST
    elif auth_header.startswith('token '):
        return TOKEN
    elif all(ApiKeyAuthentication().extract_credentials(request)):
        return API_KEY

    return default


def determine_authtype_from_request(request, default=DIGEST):
    """
    Guess the auth type, based on the (phone's) user agent or the
    headers found in the request.
    """
    user_agent = request.META.get('HTTP_USER_AGENT')
    if is_probably_j2me(user_agent):
        return DIGEST
    return determine_authtype_from_header(request, default)


def is_probably_j2me(user_agent):
    j2me_pattern = '[Nn]okia|NOKIA|CLDC|cldc|MIDP|midp|Series60|Series40|[Ss]ymbian|SymbOS|[Mm]aemo'
    return user_agent and re.search(j2me_pattern, user_agent)


def get_username_and_password_from_request(request):
    """Returns tuple of (username, password). Tuple values
    may be null."""
    from corehq.apps.hqwebapp.utils import decode_password

    if 'HTTP_AUTHORIZATION' not in request.META:
        return None, None

    def _decode(string):
        try:
            return string.decode('utf-8')
        except UnicodeDecodeError:
            # https://sentry.io/dimagi/commcarehq/issues/391378081/
            return string.decode('latin1')

    auth = request.META['HTTP_AUTHORIZATION'].split()
    username = password = None
    if auth[0].lower() == DIGEST:
        try:
            digest = parse_digest_credentials(request.META['HTTP_AUTHORIZATION'])
            username = digest.username
        except UnicodeDecodeError:
            pass
    elif auth[0].lower() == BASIC:
        username, password = base64.b64decode(auth[1]).split(':', 1)
        # decode password submitted from mobile app login
        password = decode_password(password)
        username, password = _decode(username), _decode(password)
    return username, password


def basicauth(realm=''):
    # stolen and modified from: https://djangosnippets.org/snippets/243/
    def real_decorator(view):
        def wrapper(request, *args, **kwargs):
            uname, passwd = get_username_and_password_from_request(request)
            if uname and passwd:
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


def tokenauth(view):

    @wraps(view)
    def _inner(request, *args, **kwargs):
        if not ANONYMOUS_WEB_APPS_USAGE.enabled(request.domain):
            return HttpResponse(status=401)
        try:
            user, token = TokenAuthentication().authenticate(request)
        except AuthenticationFailed as e:
            return HttpResponse(e, status=401)

        if user.is_active:
            request.user = user
            return view(request, *args, **kwargs)
        else:
            return HttpResponse('Inactive user', status=401)
    return _inner
