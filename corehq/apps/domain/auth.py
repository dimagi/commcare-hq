import base64
import binascii
import logging
import requests
from functools import wraps

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import HttpResponse
from django.views.decorators.debug import sensitive_variables

from no_exceptions.exceptions import Http400
from python_digest import parse_digest_credentials
from tastypie.authentication import ApiKeyAuthentication

from django.utils import timezone
from dimagi.utils.django.request import mutable_querydict
from dimagi.utils.web import get_ip

from corehq.apps.receiverwrapper.util import DEMO_SUBMIT_MODE
from corehq.apps.users.models import CouchUser, HQApiKey, ConnectIDUserLink
from corehq.toggles import TWO_STAGE_USER_PROVISIONING
from corehq.util.hmac_request import validate_request_hmac
from corehq.util.metrics import metrics_counter

auth_logger = logging.getLogger("commcare_auth")

ANDROID = 'android'

BASIC = 'basic'
DIGEST = 'digest'
NOAUTH = 'noauth'
API_KEY = 'api_key'
OAUTH2 = 'oauth2'
FORMPLAYER = 'formplayer'


def _is_api_key_authentication(request):
    authorization_header = request.META.get('HTTP_AUTHORIZATION', '')

    api_key_authentication = HQApiKeyAuthentication()
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
    elif auth_header.startswith('bearer '):
        return OAUTH2
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

    return determine_authtype_from_header(request, default)


@sensitive_variables('auth', 'password')
def get_username_and_password_from_request(request):
    """Returns tuple of (username, password). Tuple values
    may be null."""

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
        try:
            username, password = _decode(base64.b64decode(auth[1])).split(':', 1)
        except binascii.Error:
            return None, None
        username = username.lower()
    return username, password


def basicauth(realm=''):
    # stolen and modified from: https://djangosnippets.org/snippets/243/
    def real_decorator(view):
        def wrapper(request, *args, **kwargs):
            uname, passwd = get_username_and_password_from_request(request)
            if uname and passwd:
                user = authenticate(username=uname, password=passwd, request=request)
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
    return validate_request_hmac('FORMPLAYER_INTERNAL_AUTH_KEY')(view)


def formplayer_as_user_auth(view):
    """Auth decorator for requests coming from Formplayer that are authenticated
    using the shared key.

    All requests with this decorator require the `as` param in order to simulate auth by that user.
    This is used by SMS forms.
    """

    @wraps(view)
    def _inner(request, *args, **kwargs):
        with mutable_querydict(request.GET):
            request_user = request.GET.pop('as', None)

        if not request_user:
            auth_logger.info(
                "Request rejected reason=%s request=%s",
                "formplayer_auth:user_required", request.path
            )
            return HttpResponse('User required', status=401)

        couch_user = CouchUser.get_by_username(request_user[-1])
        if not couch_user:
            auth_logger.info(
                "Request rejected reason=%s request=%s",
                "formplayer_auth:unknown_user", request.path
            )
            return HttpResponse('Unknown user', status=401)

        request.user = couch_user.get_django_user()
        request.couch_user = couch_user

        return view(request, *args, **kwargs)

    return validate_request_hmac('FORMPLAYER_INTERNAL_AUTH_KEY')(_inner)


class ApiKeyFallbackBackend(object):

    def authenticate(self, request, username, password):
        if not getattr(request, 'check_for_password_as_api_key', False):
            return None

        try:
            user = User.objects.get(username=username, api_keys__key=password)
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            return None
        else:
            request.skip_two_factor_check = True
            return user


def get_active_users_by_email(email):
    UserModel = get_user_model()
    possible_users = UserModel._default_manager.filter(
        Q(username__iexact=email) | Q(email__iexact=email),
        is_active=True,
    )
    for user in possible_users:
        # all exact username matches should be included
        if user.username.lower() == email.lower():
            yield user
        else:
            # also any mobile workers from TWO_STAGE_USER_PROVISIONING domains should be included
            couch_user = CouchUser.get_by_username(user.username, strict=True)
            if (couch_user
                    and couch_user.is_commcare_user()
                    and TWO_STAGE_USER_PROVISIONING.enabled(couch_user.domain)):
                yield user
            # intentionally excluded:
            # - WebUsers who have changed their email address from their login (though could revisit this)
            # - CommCareUsers not belonging to domains with TWO_STAGE_USER_PROVISIONING enabled


class HQApiKeyAuthentication(ApiKeyAuthentication):
    def __init__(self, *args, allow_creds_in_data=True, **kwargs):
        self._allow_creds_in_data = allow_creds_in_data
        super().__init__(*args, **kwargs)

    def is_authenticated(self, request):
        """Follows what tastypie does, then tests for IP whitelisting
        """
        try:
            username, api_key = self.extract_credentials(request)
        except ValueError:
            return self._unauthorized()

        if not username or not api_key:
            return self._unauthorized()

        User = get_user_model()

        lookup_kwargs = {User.USERNAME_FIELD: username}
        try:
            user = User.objects.prefetch_related("api_keys").get(**lookup_kwargs)
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            return self._unauthorized()

        if not self.check_active(user):
            return False

        # ensure API Key exists
        try:
            key = user.api_keys.get(key=api_key)
        except HQApiKey.DoesNotExist:
            return self._unauthorized()

        # update api_key.last used every 30 seconds
        if key.last_used is None or (timezone.now() - key.last_used).total_seconds() > 30:
            key.last_used = timezone.now()
            key.save()

        # ensure the IP address is in the allowlist, if that exists
        if key.ip_allowlist and (get_ip(request) not in key.ip_allowlist):
            return self._unauthorized()

        request.user = user
        request.api_key = key
        return True

    def get_identifier(self, request):
        """Returns {domain}_{api_key} for use in rate limiting api key.

        Each api key can currently be used on multiple domains, and rates
        are domain specific.

        """
        # inline to avoid circular import
        from corehq.apps.api.resources.auth import ApiIdentifier

        username = self.extract_credentials(request)[0]
        domain = getattr(request, 'domain', '')
        return ApiIdentifier(username=username, domain=domain)

    def extract_credentials(self, request):
        """Extract username and key from request"""
        # This overrides an existing tastypie method
        try:
            data = self.get_authorization_data(request)
        except ValueError:
            if self._allow_creds_in_data:
                username = request.GET.get('username') or request.POST.get('username')
                api_key = request.GET.get('api_key') or request.POST.get('api_key')
                if username and api_key:
                    metrics_counter('commcare.auth.credentials_in_data', tags={
                        'domain': getattr(request, 'domain', None),
                        'request_method': request.method,
                    })
            else:
                username, api_key = None, None
        else:
            username, api_key = data.split(':', 1)

        return username, api_key


def get_connectid_userinfo(token):
    user_info = f"{settings.CONNECTID_USERINFO_URL}"
    user = requests.get(user_info, headers={"AUTHORIZATION": f"Bearer {token}"})
    connect_username = user.json().get("sub")
    return connect_username


class ConnectIDAuthBackend:

    def authenticate(self, request, username, password):
        """
        Django authentication backend for requests that authenticate with tokens from ConnectID
        This is currently only allowed for the oauth token view, and is used to generate an oauth token
        in HQ, given a ConnectID token.

        username: the username of an HQ mobile worker that has already been linked to a ConnectID user
        password: an oauth access token issued by ConnectID
        """
        # Only allow for the token backend, for now
        if not request or not request.path == '/oauth/token/':
            return None
        couch_user = CouchUser.get_by_username(username)
        if couch_user is None:
            return None
        connect_username = get_connectid_userinfo(password)
        if connect_username is None:
            return None
        link = ConnectIDUserLink.objects.get(
            connectid_username=connect_username,
            domain=couch_user.domain,
            commcare_user__username=couch_user.username
        )

        return link.commcare_user


def user_can_access_domain_specific_pages(request):
    """
        An active logged-in user can access domain specific pages if
        domain is active &
        they are a member of the domain or
        a superuser and domain does not restrict superusers from access
    """
    from corehq.apps.domain.decorators import (
        _ensure_request_couch_user,
        _ensure_request_project,
        active_user_logged_in,
    )

    if not active_user_logged_in(request):
        return False

    project = _ensure_request_project(request)
    if not (project and project.is_active):
        return False

    couch_user = _ensure_request_couch_user(request)
    if not couch_user:
        return False

    return couch_user.is_member_of(project) or (couch_user.is_superuser and not project.restrict_superusers)
