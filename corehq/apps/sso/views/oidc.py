from django.http import Http404, HttpResponseRedirect

from corehq.apps.sso.decorators import identity_provider_required
from corehq.apps.sso.utils.oidc import (
    get_client_for_identity_provider,
    initialize_oidc_session,
    get_openid_provider_login_url,
)


@identity_provider_required
def sso_oidc_login(request, idp_slug):
    client = get_client_for_identity_provider(request.idp)
    initialize_oidc_session(request)
    login_url = get_openid_provider_login_url(client, request)
    return HttpResponseRedirect(login_url)


@identity_provider_required
def sso_oidc_auth(request, idp_slug):
    # todo this is a temporary placeholder view
    raise Http404()


@identity_provider_required
def sso_oidc_logout(request, idp_slug):
    # todo this is a temporary placeholder view
    raise Http404()
