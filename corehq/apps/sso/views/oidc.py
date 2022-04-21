from django.http import Http404

from corehq.apps.sso.decorators import identity_provider_required


@identity_provider_required
def sso_oidc_login(request, idp_slug):
    # todo this is a temporary placeholder view
    raise Http404()


@identity_provider_required
def sso_oidc_auth(request, idp_slug):
    # todo this is a temporary placeholder view
    raise Http404()


@identity_provider_required
def sso_oidc_logout(request, idp_slug):
    # todo this is a temporary placeholder view
    raise Http404()
