from __future__ import absolute_import
from __future__ import unicode_literals
import base64
import re
from functools import wraps

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.views.decorators.debug import sensitive_variables
from tastypie.authentication import ApiKeyAuthentication

from corehq.apps.users.models import CouchUser
from corehq.apps.receiverwrapper.util import DEMO_SUBMIT_MODE
from corehq.util.hmac_request import validate_request_hmac
from dimagi.utils.django.request import mutable_querydict
from python_digest import parse_digest_credentials

from no_exceptions.exceptions import Http400

J2ME = 'j2me'
ANDROID = 'android'

BASIC = 'basic'
DIGEST = 'digest'
NOAUTH = 'noauth'
API_KEY = 'api_key'
FORMPLAYER = 'formplayer'


def _is_api_key_authentication(request):
    authorization_header = request.META.get('HTTP_AUTHORIZATION', '')

    api_key_authentication = ApiKeyAuthentication()
    try:
        username, api_key = api_key_authentication.extract_credentials(request)
    except ValueError:
        raise Http400("Bad HTTP_AUTHORIZATION header {}"
                      .format(authorization_header))
    else:
        return username and api_key


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
    elif _is_api_key_authentication(request):
        return API_KEY

    if request.META.get('HTTP_X_MAC_DIGEST', None):
        return FORMPLAYER

    return default


def determine_authtype_from_request(request, default=DIGEST):
    """
    Guess the auth type, based on the (phone's) user agent or the
    headers found in the request.
    """

    # Fixes behavior for mobile versions between 2.39.0 and
    # 2.46.0, which did not explicitly request noauth when
    # submitting in demo mode.
    if request.GET.get('submit_mode') == DEMO_SUBMIT_MODE:
        return NOAUTH

    user_agent = request.META.get('HTTP_USER_AGENT')
    if is_probably_j2me(user_agent):
        return DIGEST
    return determine_authtype_from_header(request, default)


def is_probably_j2me(user_agent):
    j2me_pattern = '[Nn]okia|NOKIA|CLDC|cldc|MIDP|midp|Series60|Series40|[Ss]ymbian|SymbOS|[Mm]aemo'
    return user_agent and re.search(j2me_pattern, user_agent)


@sensitive_variables('auth', 'password')
def get_username_and_password_from_request(request):
    """Returns tuple of (username, password). Tuple values
    may be null."""
    from corehq.apps.hqwebapp.utils import decode_password

    if 'HTTP_AUTHORIZATION' not in request.META:
        return None, None

    @sensitive_variables()
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
            username = digest.username.lower()
        except UnicodeDecodeError:
            pass
    elif auth[0].lower() == BASIC:
        username, password = _decode(base64.b64decode(auth[1])).split(':', 1)
        username = username.lower()
        # decode password submitted from mobile app login
        password = decode_password(password, username)
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


def basic_or_api_key(realm=''):
    def real_decorator(view):
        def wrapper(request, *args, **kwargs):
            username, password = get_username_and_password_from_request(request)
            if username and password:
                request.check_for_password_as_api_key = True
                user = authenticate(username=username, password=password, request=request)
                if user is not None and user.is_active:
                    request.user = user
                    return view(request, *args, **kwargs)
            response = HttpResponse(status=401)
            response['WWW-Authenticate'] = 'Basic realm="%s"' % realm
            return response
        return wrapper
    return real_decorator


def formplayer_auth(view):
    return validate_request_hmac('FORMPLAYER_INTERNAL_AUTH_KEY', ignore_if_debug=True)(view)


def formplayer_as_user_auth(view):
    """Auth decorator for requests coming from Formplayer that are authenticated
    using the shared key.

    All requests with this decorator require the `as` param in order to simulate auth by that user.
    This is used by SMS forms.
    """

    @wraps(view)
    def _inner(request, *args, **kwargs):
        with mutable_querydict(request.GET):
            as_user = request.GET.pop('as', None)

        if not as_user:
            return HttpResponse('User required', status=401)

        couch_user = CouchUser.get_by_username(as_user[-1])
        if not couch_user:
            return HttpResponse('Unknown user', status=401)

        request.user = couch_user.get_django_user()
        request.couch_user = couch_user

        return view(request, *args, **kwargs)

    return validate_request_hmac('FORMPLAYER_INTERNAL_AUTH_KEY', ignore_if_debug=True)(_inner)


class ApiKeyFallbackBackend(object):

    def authenticate(self, request, username, password):
        if not getattr(request, 'check_for_password_as_api_key', False):
            return None

        try:
            user = User.objects.get(username=username, api_key__key=password)
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            return None
        else:
            request.skip_two_factor_check = True
            return user
