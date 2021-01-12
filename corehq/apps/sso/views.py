import json

from django.http import (
    HttpResponse,
    HttpResponseServerError,
    HttpResponseRedirect,
)

from django.conf import settings
from django.urls import reverse
from django.shortcuts import render

from onelogin.saml2.settings import OneLogin_Saml2_Settings
from onelogin.saml2.utils import OneLogin_Saml2_Utils

from corehq.apps.sso.decorators import (
    identity_provider_required,
    use_saml2_auth,
)
from corehq.apps.sso.configuration import get_saml2_config


## for debugging
def init_saml_auth(req):
    auth = req.saml2_auth
    return auth


def prepare_django_request(request):
    # If server is behind proxys or balancers use the HTTP_X_FORWARDED fields
    result = {
        'https': 'on' if request.is_secure() else 'off',
        'http_host': request.META['HTTP_HOST'],
        'script_name': request.META['PATH_INFO'],
        'server_port': request.META['SERVER_PORT'],
        'get_data': request.GET.copy(),
        # Uncomment if using ADFS as IdP, https://github.com/onelogin/python-saml/pull/144
        # 'lowercase_urlencoding': True,
        'post_data': request.POST.copy()
    }
    return result


@use_saml2_auth
def index(request):
    req = prepare_django_request(request)
    auth = init_saml_auth(request)
    errors = []
    error_reason = None
    not_auth_warn = False
    success_slo = False
    attributes = False
    paint_logout = False

    if 'sso' in req['get_data']:
        return HttpResponseRedirect(auth.login())
        # If AuthNRequest ID need to be stored in order to later validate it, do instead
        # sso_built_url = auth.login()
        # request.session['AuthNRequestID'] = auth.get_last_request_id()
        # return HttpResponseRedirect(sso_built_url)
    elif 'sso2' in req['get_data']:
        return_to = OneLogin_Saml2_Utils.get_self_url(req) + reverse('attrs')
        return HttpResponseRedirect(auth.login(return_to))
    elif 'slo' in req['get_data']:
        name_id = session_index = name_id_format = name_id_nq = name_id_spnq = None
        if 'samlNameId' in request.session:
            name_id = request.session['samlNameId']
        if 'samlSessionIndex' in request.session:
            session_index = request.session['samlSessionIndex']
        if 'samlNameIdFormat' in request.session:
            name_id_format = request.session['samlNameIdFormat']
        if 'samlNameIdNameQualifier' in request.session:
            name_id_nq = request.session['samlNameIdNameQualifier']
        if 'samlNameIdSPNameQualifier' in request.session:
            name_id_spnq = request.session['samlNameIdSPNameQualifier']

        return HttpResponseRedirect(auth.logout(name_id=name_id, session_index=session_index, nq=name_id_nq, name_id_format=name_id_format, spnq=name_id_spnq))
        # If LogoutRequest ID need to be stored in order to later validate it, do instead
        # slo_built_url = auth.logout(name_id=name_id, session_index=session_index)
        # request.session['LogoutRequestID'] = auth.get_last_request_id()
        # return HttpResponseRedirect(slo_built_url)
    elif 'acs' in req['get_data']:
        request_id = None
        if 'AuthNRequestID' in request.session:
            request_id = request.session['AuthNRequestID']

        auth.process_response(request_id=request_id)
        errors = auth.get_errors()
        not_auth_warn = not auth.is_authenticated()

        if not errors:
            if 'AuthNRequestID' in request.session:
                del request.session['AuthNRequestID']
            request.session['samlUserdata'] = auth.get_attributes()
            request.session['samlNameId'] = auth.get_nameid()
            request.session['samlNameIdFormat'] = auth.get_nameid_format()
            request.session['samlNameIdNameQualifier'] = auth.get_nameid_nq()
            request.session['samlNameIdSPNameQualifier'] = auth.get_nameid_spnq()
            request.session['samlSessionIndex'] = auth.get_session_index()
            if 'RelayState' in req['post_data'] and OneLogin_Saml2_Utils.get_self_url(req) != req['post_data']['RelayState']:
                return HttpResponseRedirect(auth.redirect_to(req['post_data']['RelayState']))
        elif auth.get_settings().is_debug_active():
                error_reason = auth.get_last_error_reason()
    elif 'sls' in req['get_data']:
        request_id = None
        if 'LogoutRequestID' in request.session:
            request_id = request.session['LogoutRequestID']
        dscb = lambda: request.session.flush()
        url = auth.process_slo(request_id=request_id, delete_session_cb=dscb)
        errors = auth.get_errors()
        if len(errors) == 0:
            if url is not None:
                return HttpResponseRedirect(url)
            else:
                success_slo = True
        elif auth.get_settings().is_debug_active():
            error_reason = auth.get_last_error_reason()

    if 'samlUserdata' in request.session:
        paint_logout = True
        if len(request.session['samlUserdata']) > 0:
            attributes = request.session['samlUserdata'].items()

    return render(request, 'sso/index.html', {'errors': errors, 'error_reason': error_reason, 'not_auth_warn': not_auth_warn, 'success_slo': success_slo,
                                          'attributes': attributes, 'paint_logout': paint_logout})


@identity_provider_required
def attrs(request, idp_slug):
    paint_logout = False
    attributes = False

    if 'samlUserdata' in request.session:
        paint_logout = True
        if len(request.session['samlUserdata']) > 0:
            attributes = request.session['samlUserdata'].items()
    return render(request, 'sso/attrs.html',
                  {'paint_logout': paint_logout,
                   'attributes': attributes})


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

    request_id = request.session.get('AuthNRequestID')
    request.saml2_auth.process_response(request_id=request_id)
    errors = request.saml2_auth.get_errors()
    not_auth_warn = not request.saml2_auth.is_authenticated()

    if not errors:
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
    return HttpResponseRedirect(request.saml2_auth.login())


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
