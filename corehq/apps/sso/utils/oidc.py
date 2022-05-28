from oic.oauth2 import AuthorizationResponse, ErrorResponse, ResponseError
from oic.oic import Client, RegistrationResponse
from oic.utils.authn.client import CLIENT_AUTHN_METHOD
from oic import rndstr

from corehq.apps.sso.exceptions import (
    OidcSsoError,
    SsoLoginFailed,
)
from corehq.apps.sso.utils.request_helpers import get_return_to_url_from_request
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
    request.session["oidc_return_to"] = get_return_to_url_from_request(request)


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


def get_user_information_or_throw_error(client, request):
    try:
        auth_or_error_response = client.parse_response(
            AuthorizationResponse,
            info=request.GET.urlencode(),
            sformat="urlencoded",
        )
    except ResponseError:
        raise OidcSsoError(OidcSsoError.METHOD_NOT_ALLOWED)

    if isinstance(auth_or_error_response, ErrorResponse):
        error_data = auth_or_error_response.to_dict()
        raise OidcSsoError(OidcSsoError.OP_ERROR_MESSAGE, message=error_data['error_description'])

    if auth_or_error_response["state"] != request.session["oidc_state"]:
        raise OidcSsoError(OidcSsoError.SESSION_UNKNOWN)

    access_response = client.do_access_token_request(
        state=auth_or_error_response["state"],
        request_args={
            "code": auth_or_error_response["code"],
        },
        authn_method="client_secret_post"
    )

    if isinstance(access_response, ErrorResponse):
        raise SsoLoginFailed()

    user_info = client.do_user_info_request(
        state=auth_or_error_response["state"],
    )

    if isinstance(user_info, ErrorResponse):
        raise OidcSsoError(OidcSsoError.USER_PERMISSION_ISSUE)

    return user_info
