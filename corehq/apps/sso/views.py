import json

from django.http import (
    HttpResponse,
    HttpResponseServerError,
    HttpResponseRedirect,
)
from onelogin.saml2.settings import OneLogin_Saml2_Settings
from onelogin.saml2.utils import OneLogin_Saml2_Utils

from corehq.util.soft_assert import soft_assert
from corehq.apps.sso.decorators import (
    identity_provider_required,
    use_saml2_auth,
)
from corehq.apps.sso.configuration import get_saml2_config


sso_soft_assert = soft_assert(
    to=['{}@{}'.format('biyeun', 'dimagi.com')],
    send_to_ops=False
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
def sso_saml_acs(request, idp_slug):
    """
    ACS stands for "Assertion Consumer Service". The Identity Provider will send
    its response to this view after authenticating a user. This is often
    referred to as the "Entity ID" in the IdP's Service Provider configuration.

    In this view we verify the received SAML 2.0 response and then log in the user
    to CommCare HQ.
    """
    # todo these are placeholders for the json dump below
    error_reason = None
    success_slo = False
    attributes = False
    saml_user_data_present = False

    try:
        request_id = request.session.get('AuthNRequestID')
        request.saml2_auth.process_response(request_id=request_id)
        sso_soft_assert(False, 'auth processed')
        errors = request.saml2_auth.get_errors()
        not_auth_warn = not request.saml2_auth.is_authenticated()
    except Exception as e:
        sso_soft_assert(False, 'reached exception')
        errors = [e]
        not_auth_warn = True

    if not errors:
        sso_soft_assert(False, 'not errors')
        if 'AuthNRequestID' in request.session:
            del request.session['AuthNRequestID']

        request.session['samlUserdata'] = request.saml2_auth.get_attributes()
        request.session['samlNameId'] = request.saml2_auth.get_nameid()
        request.session['samlNameIdFormat'] = request.saml2_auth.get_nameid_format()
        request.session['samlNameIdNameQualifier'] = request.saml2_auth.get_nameid_nq()
        request.session['samlNameIdSPNameQualifier'] = request.saml2_auth.get_nameid_spnq()
        request.session['samlSessionIndex'] = request.saml2_auth.get_session_index()

        if ('RelayState' in request.POST
            and OneLogin_Saml2_Utils.get_self_url(request) != request.POST['RelayState']
        ):
            return HttpResponseRedirect(request.saml2_auth.redirect_to(request.POST['RelayState']))
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
        "not_auth_warn": not_auth_warn,
        "success_slo": success_slo,
        "attributes": attributes,
        "saml_user_data_present": saml_user_data_present,
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
    if request.saml2_errors:
        return HttpResponse(json.dumps({
            "errors": request.saml2_errors,
            "request_data": request.saml2_request_data,
        }), 'text/json')
    try:
        return HttpResponseRedirect(request.saml2_auth.login(set_nameid_policy=True))
    except Exception as e:
        return HttpResponse(json.dumps({
            "errors": e,
            "failure_point": 'after redirect',
            "request_data": request.saml2_request_data,
        }), 'text/json')



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
