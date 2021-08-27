import logging
from functools import wraps

from django.http import Http404
from django.shortcuts import render
from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.errors import OneLogin_Saml2_Error

from corehq.apps.sso.models import IdentityProvider
from corehq.apps.sso.configuration import get_saml2_config
from corehq.apps.sso.utils.request_helpers import get_request_data
from corehq.apps.sso.utils.url_helpers import get_documentation_url

logger = logging.getLogger(__name__)


def identity_provider_required(view_func):
    @wraps(view_func)
    def _inner(request, idp_slug, *args, **kwargs):
        request.idp = _get_idp_or_404(idp_slug)
        return view_func(request, idp_slug, *args, **kwargs)
    return _inner


def use_saml2_auth(view_func):
    @wraps(view_func)
    def _inner(request, idp_slug, *args, **kwargs):
        request.idp = _get_idp_or_404(idp_slug)
        request.saml2_request_data = get_request_data(request)
        try:
            request.saml2_auth = OneLogin_Saml2_Auth(
                request.saml2_request_data, get_saml2_config(request.idp)
            )
        except OneLogin_Saml2_Error as e:
            if (request.idp.is_active
                    and e.code != OneLogin_Saml2_Error.REDIRECT_INVALID_URL):
                logger.error(
                    f"An active Identity Provider {idp_slug} appears to have "
                    f"an SSO configuration issue. Please look into this "
                    f"immediately! {str(e)}"
                )
            elif e.code not in [
                OneLogin_Saml2_Error.SETTINGS_INVALID,
                OneLogin_Saml2_Error.CERT_NOT_FOUND,
                OneLogin_Saml2_Error.REDIRECT_INVALID_URL
            ]:
                logger.error(
                    f"An inactive Identity Provider {idp_slug} appears to have "
                    f"an SSO configuration issue. Please take note of this "
                    f"error if an Enterprise Admin reaches out for support: "
                    f"error code {e.code}, {str(e)}"
                )
            return render(request, 'sso/config_errors.html', {
                'idp_is_active': request.idp.is_active,
                'idp_name': request.idp.name,
                'error': e,
                'docs_link': get_documentation_url(request.idp),
            })

        return view_func(request, idp_slug, *args, **kwargs)
    return _inner


def _get_idp_or_404(idp_slug):
    idp = IdentityProvider.objects.filter(slug=idp_slug).first()
    if not idp:
        raise Http404()
    return idp
