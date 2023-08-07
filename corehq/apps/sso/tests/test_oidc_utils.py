from testil import eq

from django.test import RequestFactory

from corehq.apps.sso.utils.oidc import initialize_oidc_session


def test_initialize_oidc_session():
    request = RequestFactory().get('/sso/test')
    request.session = {}
    request.GET = {
        'next': '/next/path',
    }
    initialize_oidc_session(request)
    eq(request.session["oidc_state"] is not None, True)
    eq(request.session["oidc_nonce"] is not None, True)
    eq(request.session["oidc_return_to"], '/next/path')
