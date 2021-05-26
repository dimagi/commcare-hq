import json

from django.conf import settings
from django.contrib import auth, messages
from django.http import (
    HttpResponse,
    HttpResponseServerError,
    HttpResponseRedirect,
    Http404,
)
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.utils.translation import ugettext as _
from onelogin.saml2.settings import OneLogin_Saml2_Settings

from corehq.apps.domain.decorators import login_required
from corehq.apps.domain.exceptions import NameUnavailableException
from corehq.apps.registration.models import AsyncSignupRequest
from corehq.apps.registration.utils import request_new_domain
from corehq.apps.sso.decorators import (
    identity_provider_required,
    use_saml2_auth,
)
from corehq.apps.sso.configuration import get_saml2_config
from corehq.apps.sso.models import IdentityProvider
from corehq.apps.sso.utils.session_helpers import (
    store_saml_data_in_session,
    get_sso_username_from_session,
    prepare_session_with_sso_username,
)
from corehq.apps.users.models import Invitation


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
    if request.method is not 'POST':
        raise Http404()

    request_id = request.session.get('AuthNRequestID')
    request.saml2_auth.process_response(request_id=request_id)
    errors = request.saml2_auth.get_errors()

    if errors:
        return render(request, 'sso/acs_errors.html', {
            'saml_error_reason': request.saml2_auth.get_last_error_reason(),
            'idp_type': "Azure AD",  # we will update this later,
            'docs_link': '#tbd',  # we will update this later,
        })

    if not request.saml2_auth.is_authenticated():
        return render(request, 'sso/sso_request_denied.html', {})

    if 'AuthNRequestID' in request.session:
        del request.session['AuthNRequestID']

    store_saml_data_in_session(request)

    user = auth.authenticate(
        request=request,
        username=request.session['samlNameId'],
        idp_slug=idp_slug,
        is_handshake_successful=True,
    )

    # we add the messages to the django messages framework here since
    # that middleware was not available for SsoBackend
    if hasattr(request, 'sso_new_user_messages'):
        for success_message in request.sso_new_user_messages['success']:
            messages.success(request, success_message)
        for error_message in request.sso_new_user_messages['error']:
            messages.error(request, error_message)

    if user:
        auth.login(request, user)

        # activate new project if needed
        async_signup = AsyncSignupRequest.get_by_username(user.username)
        if async_signup and async_signup.project_name:
            try:
                request_new_domain(request, async_signup.project_name, is_new_user=True)
            except NameUnavailableException:
                # this should never happen, but in the off chance it does
                # we don't want to throw a 500 on this view
                messages.error(
                    request,
                    _("We were unable to create your requested project "
                      "because the name was already taken."
                      "Please contact support.")
                )

        AsyncSignupRequest.clear_data_for_username(user.username)
        return redirect("homepage")

    return render(request, 'sso/acs_errors.html', {
        'login_error': getattr(request, 'sso_login_error', None),
    })


@use_saml2_auth
@login_required
def sso_debug_user_data(request, idp_slug):
    """
    Test utility for showing SAML data on the staging environment.
    """
    if settings.SERVER_ENVIRONMENT not in ['staging']:
        raise Http404()
    return HttpResponse(json.dumps({
        "samlUserdata": request.session.get('samlUserdata'),
        "samlNameId": request.session.get('samlNameId'),
        "samlNameIdFormat": request.session.get('samlNameIdFormat'),
        "samlNameIdNameQualifier": request.session.get('samlNameIdNameQualifier'),
        "samlNameIdSPNameQualifier": request.session.get('samlNameIdSPNameQualifier'),
        "samlSessionIndex": request.session.get('samlSessionIndex'),
    }), 'text/json')


@use_saml2_auth
def sso_saml_sls(request, idp_slug):
    """
    SLS stands for Single Logout Service. This view is responsible for
    handling a logout response from the Identity Provider.
    """
    # todo these are placeholders for the json dump below
    error_reason = None
    success_slo = False
    attributes = False
    saml_user_data_present = False

    request_id = request.session.get('LogoutRequestID')
    url = request.saml2_auth.process_slo(
        request_id=request_id,
        delete_session_cb=lambda: request.session.flush()
    )
    errors = request.saml2_auth.get_errors()

    if len(errors) == 0:
        if url is not None:
            return HttpResponseRedirect(url)
        else:
            success_slo = True
    elif request.saml2_auth.get_settings().is_debug_active():
        error_reason = request.saml2_auth.get_last_error_reason()

    # todo what's below is a debugging placeholder
    if 'samlUserdata' in request.session:
        saml_user_data_present = True
        if len(request.session['samlUserdata']) > 0:
            attributes = request.session['samlUserdata'].items()

    return HttpResponse(json.dumps({
        "errors": errors,
        "error_reason": error_reason,
        "success_slo": success_slo,
        "attributes": attributes,
        "saml_user_data_present": saml_user_data_present,
    }), 'text/json')


@use_saml2_auth
def sso_saml_login(request, idp_slug):
    """
    This view initiates a SAML 2.0 login request with the Identity Provider.
    """
    login_url = request.saml2_auth.login()
    username = get_sso_username_from_session(request) or request.GET.get('username')
    if username:
        # verify that the stored user data actually the current IdP
        idp = IdentityProvider.get_active_identity_provider_by_username(username)
        if idp and idp.slug == idp_slug:
            # pre-populate username for Azure AD
            login_url = f'{login_url}&login_hint={username}'
    return HttpResponseRedirect(login_url)


@use_saml2_auth
def sso_saml_logout(request, idp_slug):
    """
    This view initiates a SAML 2.0 logout request with the Identity Provider.
    """
    return HttpResponseRedirect(request.saml2_auth.logout(
        name_id=request.session.get('samlNameId'),
        session_index=request.session.get('samlSessionIndex'),
        nq=request.session.get('samlNameIdNameQualifier'),
        name_id_format=request.session.get('samlNameIdFormat'),
        spnq=request.session.get('samlNameIdSPNameQualifier')
    ))


@use_saml2_auth
def sso_test_create_user(request, idp_slug):
    """
    A testing view exclusively for staging. This will be removed once the
    UIs are in place to sign up users or invite new users who must log in with
    SSO.
    """
    if settings.SERVER_ENVIRONMENT not in ['staging']:
        raise Http404()

    username = request.GET.get('username')
    if username:
        prepare_session_with_sso_username(request, username)

    invitation_uuid = request.GET.get('invitation')
    invitation = Invitation.objects.get(uuid=invitation_uuid) if invitation_uuid else None
    if invitation:
        AsyncSignupRequest.create_from_invitation(invitation)

    return HttpResponseRedirect(reverse("sso_saml_login", args=(idp_slug,)))
