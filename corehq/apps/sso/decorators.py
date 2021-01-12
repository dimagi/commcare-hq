from functools import wraps

from django.http import Http404
from onelogin.saml2.auth import OneLogin_Saml2_Auth

from corehq.apps.sso.models import IdentityProvider
from corehq.apps.sso.configuration import get_saml2_config


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
        try:
            request_data = {
                'https': 'on' if request.is_secure() else 'off',
                'http_host': request.META['HTTP_HOST'],
                'script_name': request.META['PATH_INFO'],
                'server_port': request.META['SERVER_PORT'],
                'get_data': request.GET.copy(),
                'post_data': request.POST.copy(),
            }
            from corehq.apps.sso.views import sso_soft_assert
            sso_soft_assert(False, request_data)
            request.saml2_auth = OneLogin_Saml2_Auth(request_data, get_saml2_config(request.idp))
            request.saml2_errors = None
        except Exception as e:
            request.saml2_errors = e
        return view_func(request, idp_slug, *args, **kwargs)
    return _inner


def _get_idp_or_404(idp_slug):
    idp = IdentityProvider.objects.filter(slug=idp_slug).first()
    if not idp:
        raise Http404()
    return idp
