from oic.oic import Client, RegistrationResponse
from oic.utils.authn.client import CLIENT_AUTHN_METHOD
from oic import rndstr

from corehq.apps.sso.utils.url_helpers import get_oidc_auth_url


def get_client_for_identity_provider(identity_provider):
    client = Client(
        client_authn_method=CLIENT_AUTHN_METHOD,
        client_id=identity_provider.client_id,
    )
    client.redirect_uris = [
        get_oidc_auth_url(identity_provider),
    ]
    client.provider_config(identity_provider.entity_id)
    security_info = {
        "client_id": identity_provider.client_id,
        "client_secret": identity_provider.client_secret,
    }
    client_reg = RegistrationResponse(**security_info)
    client.store_registration_info(client_reg)
    return client


def initialize_oidc_session(request):
    request.session["oidc_state"] = rndstr()
    request.session["oidc_nonce"] = rndstr()
    request.session["oidc_return_to"] = request.GET.get('next')


def get_openid_provider_login_url(client, request):
    args = {
        "client_id": client.client_id,
        "response_type": "code",  # note: this may change with different identity provider types
        "scope": ["openid", "profile"],  # note: this may change with different identity provider types
        "nonce": request.session["oidc_nonce"],
        "redirect_uri": get_oidc_auth_url(request.idp),
        "state": request.session["oidc_state"],
    }
    auth_req = client.construct_AuthorizationRequest(request_args=args)
    return auth_req.request(client.authorization_endpoint)
