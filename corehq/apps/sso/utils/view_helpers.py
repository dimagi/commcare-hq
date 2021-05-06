from django.shortcuts import render

from django.utils.translation import ugettext as _
from corehq.apps.sso.models import IdentityProvider


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
