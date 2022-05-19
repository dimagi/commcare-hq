from urllib.parse import urlparse

from django.conf import settings
from django.contrib import messages

from corehq.apps.sso.exceptions import SingleSignOnError
from corehq.apps.sso.models import (
    IdentityProvider,
)
from corehq.apps.sso.utils.message_helpers import (
    get_success_message_for_trusted_idp,
)


def get_request_data(request):
    """
    OneLogin's python3-saml library expects a very specifically formatted
    "request_data" object as it is framework agnostic and each framework
    (eg flask, django, tornado) has its own way of populating the built in
    request object
    :param request:
    :return: dictionary with fields that python3-saml expects
    """
    return {
        'https': ('off' if settings.SAML2_DEBUG and not request.is_secure()
                  else 'on'),
        'http_host': request.META['HTTP_HOST'],
        'script_name': request.META['PATH_INFO'],

        # see https://github.com/onelogin/python3-saml/issues/83
        'server_port': (request.META['SERVER_PORT']
                        if settings.SAML2_DEBUG else '443'),

        'get_data': request.GET.copy(),
        'post_data': request.POST.copy(),
    }


def get_return_to_url_from_request(request):
    next_url = request.GET.get('next')
    if not urlparse(next_url).netloc:
        # only accept relative urls
        return next_url


def is_request_using_sso(request):
    if not hasattr(request, 'session'):
        return False
    is_using_saml = request.session.get('samlSessionIndex') is not None
    is_using_oidc = request.session.get('oidc_state') is not None
    return is_using_saml or is_using_oidc


def is_request_blocked_from_viewing_domain_due_to_sso(request, domain_obj):
    """
    Checks whether a given request is allowed to view a domain.

    :param request: HttpRequest
    :param domain_obj: Domain object
    :return: Boolean (True if request is blocked)
    """
    if not is_request_using_sso(request):
        # Request is not using SSO, so it's never blocked
        return False

    username = request.user.username
    idp = IdentityProvider.get_active_identity_provider_by_username(username)
    if not idp:
        raise SingleSignOnError(
            f"User {username} was authenticated via SSO, but does not appear "
            f"to be associated with an Identity Provider!"
        )

    if idp.does_domain_trust_this_idp(domain_obj.name):
        return False

    if domain_obj.creating_user == username:
        # The user created this domain and thus should never be blocked.
        # However, a Trust was not yet established. Since the current user
        # owns this domain, a Trust will be created automatically and a message
        # will be displayed to the user.
        if idp.create_trust_with_domain(domain_obj.name, request.user.username):
            messages.success(
                request,
                get_success_message_for_trusted_idp(idp, domain_obj)
            )
        return False

    # None of the above criteria was met so the user is definitely blocked!
    return True
