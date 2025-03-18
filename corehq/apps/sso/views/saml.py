from django.contrib import auth
from django.http import (
    HttpResponse,
    HttpResponseServerError,
    HttpResponseRedirect,
)
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from onelogin.saml2.errors import OneLogin_Saml2_Error
from onelogin.saml2.settings import OneLogin_Saml2_Settings
from onelogin.saml2.utils import OneLogin_Saml2_Utils

from corehq.apps.sso.decorators import (
    identity_provider_required,
    use_saml2_auth,
)
from corehq.apps.sso.configuration import get_saml2_config
from corehq.apps.sso.utils.login_helpers import process_async_signup_requests
from corehq.apps.sso.utils.message_helpers import show_sso_login_success_or_error_messages
from corehq.apps.sso.utils.session_helpers import (
    store_saml_data_in_session,
)
from corehq.apps.sso.utils.url_helpers import (
    get_saml_login_url,
    add_username_hint_to_login_url,
)
from corehq.apps.sso.utils.view_helpers import (
    render_sso_user_login_failed,
    render_saml_acs_error,
)


@identity_provider_required
def sso_saml_metadata(request, idp_slug):
    """
    Returns XML with SAML 2.0 Metadata as the Service Provider (SP).
    Often referred to as the SP Identifier or SP Entity ID in the
    Identity Provider's Documentation.
    """
    saml_settings = OneLogin_Saml2_Settings(get_saml2_config(request.idp))
    metadata = saml_settings.get_sp_metadata()
    errors = saml_settings.validate_metadata(metadata)

    if len(errors) == 0:
        resp = HttpResponse(content=metadata, content_type='text/xml')
    else:
        resp = HttpResponseServerError(content=', '.join(errors))
    return resp


@use_saml2_auth
@csrf_exempt
def sso_saml_acs(request, idp_slug):
    """
    ACS stands for "Assertion Consumer Service". The Identity Provider will send
    its response to this view after authenticating a user. This is often
    referred to as the "Entity ID" in the IdP's Service Provider configuration.

    In this view we verify the received SAML 2.0 response and then log in the user
    to CommCare HQ.
    """
    request_id = request.session.get('AuthNRequestID')

    try:
        request.saml2_auth.process_response(request_id=request_id)
        errors = request.saml2_auth.get_errors()
    except OneLogin_Saml2_Error as e:
        if e.code == OneLogin_Saml2_Error.SAML_RESPONSE_NOT_FOUND:
            return redirect("sso_saml_login", idp_slug=idp_slug)
        errors = [e]

    if errors:
        return render_saml_acs_error(
            request,
            saml_error_reason=request.saml2_auth.get_last_error_reason() or errors[0],
            idp_service_name=request.idp.service_name,
        )

    if not request.saml2_auth.is_authenticated():
        return render_sso_user_login_failed(request)

    if 'AuthNRequestID' in request.session:
        del request.session['AuthNRequestID']

    store_saml_data_in_session(request)

    user = auth.authenticate(
        request=request,
        username=request.session['samlNameId'],
        idp_slug=idp_slug,
        is_handshake_successful=True,
    )

    show_sso_login_success_or_error_messages(request)

    if user:
        auth.login(request, user)
        process_async_signup_requests(request, user)

        relay_state = request.saml2_request_data['post_data'].get('RelayState')
        if relay_state not in [
            OneLogin_Saml2_Utils.get_self_url(request.saml2_request_data),
            get_saml_login_url(request.idp),
        ]:
            # redirect to next=<relay_state>
            return HttpResponseRedirect(
                request.saml2_auth.redirect_to(relay_state)
            )

        return redirect("homepage")

    return render_saml_acs_error(
        request,
        login_error=getattr(request, 'sso_login_error', None),
    )


@use_saml2_auth
def sso_saml_login(request, idp_slug):
    """
    This view initiates a SAML 2.0 login request with the Identity Provider.
    """
    login_url = add_username_hint_to_login_url(
        request.saml2_auth.login(return_to=request.GET.get('next'), force_authn=True),
        request
    )
    return HttpResponseRedirect(login_url)
