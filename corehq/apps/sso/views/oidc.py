from django.contrib import auth
from django.contrib.auth import logout
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect

from corehq.util.view_utils import reverse
from corehq.apps.sso.decorators import identity_provider_required
from corehq.apps.sso.exceptions import SsoLoginFailed, OidcSsoError
from corehq.apps.sso.utils.login_helpers import process_async_signup_requests
from corehq.apps.sso.utils.message_helpers import show_sso_login_success_or_error_messages
from corehq.apps.sso.utils.oidc import (
    get_client_for_identity_provider,
    initialize_oidc_session,
    get_openid_provider_login_url,
    get_user_information_or_throw_error,
)
from corehq.apps.sso.utils.url_helpers import add_username_hint_to_login_url
from corehq.apps.sso.utils.view_helpers import render_sso_error, render_sso_user_login_failed


@identity_provider_required
def sso_oidc_login(request, idp_slug):
    client = get_client_for_identity_provider(request.idp)
    initialize_oidc_session(request)
    login_url = add_username_hint_to_login_url(
        get_openid_provider_login_url(client, request),
        request
    )
    return HttpResponseRedirect(login_url)


@identity_provider_required
def sso_oidc_auth(request, idp_slug):
    client = get_client_for_identity_provider(request.idp)
    try:
        user_info = get_user_information_or_throw_error(client, request)
        request.session['oidcUserData'] = user_info
        username = user_info['email'] if 'email' in user_info else user_info['preferred_username']
        user = auth.authenticate(
            request=request,
            username=username,
            idp_slug=idp_slug,
            is_handshake_successful=True,
        )
        show_sso_login_success_or_error_messages(request)

        if user:
            auth.login(request, user)
            process_async_signup_requests(request, user)

            if request.session["oidc_return_to"]:
                redirect_url = request.session["oidc_return_to"]
                del request.session["oidc_return_to"]
                return HttpResponseRedirect(redirect_url)

            return redirect("homepage")

    except OidcSsoError as error:
        return render_sso_error(request, error)
    except SsoLoginFailed:
        return render_sso_user_login_failed(request)
    return JsonResponse({
        "issue": True,
    })


@identity_provider_required
def sso_oidc_logout(request, idp_slug):
    # Only the OP would ever redirect to this view. We don't handle logging out from the OP.
    logout(request)
    return HttpResponseRedirect(reverse('login'))
