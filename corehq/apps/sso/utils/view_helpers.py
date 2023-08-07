from django.shortcuts import render

from django.utils.translation import gettext as _
from corehq.apps.sso.models import IdentityProvider, IdentityProviderProtocol
from corehq.apps.sso.utils.url_helpers import get_documentation_url


def render_untrusted_identity_provider_for_domain_view(request, domain):
    """
    This is a "faux" view that doesn't map to a url, but returns a rendered
    page response which alerts the user that they do not have access (based
    on unmet sso requirements) to view this Domain.

    :param request: HttpRequest
    :param domain: Domain (object)
    :return: HttpResponse
    """
    identity_provider = IdentityProvider.get_active_identity_provider_by_username(
        request.user.username
    )
    template = "sso/permissions/untrusted_identity_provider_for_domain.html"
    context = {
        'section': {
            'page_name': domain.name,
        },
        'current_page': {
            'title': _("Untrusted Identity Provider"),
            'page_name': _("Untrusted Identity Provider"),
        },
        'domain': domain.name,
        'identity_provider': identity_provider.name,
    }
    return render(request, template, context)


def render_sso_error(request, error):
    return render(request, 'sso/config_errors.html', {
        'idp_is_active': request.idp.is_active,
        'idp_name': request.idp.name,
        'error': error,
        'docs_link': get_documentation_url(request.idp),
        'is_saml': request.idp.protocol == IdentityProviderProtocol.SAML,
        'is_oidc': request.idp.protocol == IdentityProviderProtocol.OIDC,
    })


def render_sso_user_login_failed(request):
    return render(request, 'sso/sso_request_denied.html', {})


def render_saml_acs_error(request, saml_error_reason=None, idp_service_name=None, login_error=None):
    return render(request, 'sso/acs_errors.html', {
        'saml_error_reason': saml_error_reason,
        'idp_type': idp_service_name,
        'docs_link': get_documentation_url(request.idp),
        'login_error': login_error,
    })
