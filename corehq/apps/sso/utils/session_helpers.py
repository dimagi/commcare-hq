import logging

from corehq.apps.users.models import Invitation

log = logging.getLogger(__name__)


def store_saml_data_in_session(request):
    """
    This stores SAML-related authentication data in the request's session
    :param request: HttpRequest
    """
    request.session['samlUserdata'] = request.saml2_auth.get_attributes()
    request.session['samlNameId'] = request.saml2_auth.get_nameid()
    request.session['samlNameIdFormat'] = request.saml2_auth.get_nameid_format()
    request.session['samlNameIdNameQualifier'] = request.saml2_auth.get_nameid_nq()
    request.session['samlNameIdSPNameQualifier'] = request.saml2_auth.get_nameid_spnq()
    request.session['samlSessionIndex'] = request.saml2_auth.get_session_index()


def get_sso_user_first_name_from_session(request):
    """
    This gets the first name from sso user data stored in the session SAML data.
    :param request: HttpRequest
    :return: string or None
    """
    return request.session.get('samlUserdata', {}).get(
        'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname'
    )


def get_sso_user_last_name_from_session(request):
    """
    This gets the last name from sso user data stored in the session SAML data.
    :param request: HttpRequest
    :return: string or None
    """
    return request.session.get('samlUserdata', {}).get(
        'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname'
    )


def prepare_session_for_sso_invitation(request, invitation):
    """
    This prepares the Request's Session to store invitation details for use
    when logging in as a new or existing user through SSO.
    :param request: HttpRequest
    :param invitation: Invitation
    """
    request.session['ssoInvitation'] = invitation.uuid


def get_sso_invitation_from_session(request):
    """
    Fetches an Invitation object from the ssoInvitation information
    (if available) stored in the request session.
    :param request: HttpRequest
    :return: Invitation or None
    """
    uuid = request.session.get('ssoInvitation')
    try:
        return Invitation.objects.get(uuid=uuid) if uuid else None
    except Invitation.DoesNotExist:
        log.exception(
            f"Error fetching invitation from sso create user request: {uuid}"
        )


def prepare_session_with_sso_username(request, username):
    """
    Prepares the request's Session to store username information related to
    a user that is signing up or a user that is signing in using SSO from
    a registration, invitation, or sign in form.
    :param request: HttpRequest
    :param username: string - username / email
    """
    request.session['ssoNewUsername'] = username


def get_sso_username_from_session(request):
    """
    If present, this gets the ssoUsername stored in the request's session.
    :param request: HttpRequest
    :return: string or None - username
    """
    return request.session.get('ssoNewUsername')


def prepare_session_with_new_sso_user_data(request, reg_form,
                                           additional_hubspot_data=None):
    """
    Prepares the Request's Session to store registration form details
    when a user is signing up for an account on HQ and using SSO to login.
    :param request: HttpRequest
    :param reg_form: RegisterWebUserForm
    :param additional_hubspot_data: dict or None (Hubspot related data from A/B tests etc)
    """
    persona = reg_form.cleaned_data['persona']
    persona_other = reg_form.cleaned_data['persona_other']
    additional_hubspot_data = additional_hubspot_data or {}
    additional_hubspot_data.update({
        'buyer_persona': persona,
        'buyer_persona_other': persona_other,
    })

    request.session['ssoNewUserData'] = {
        'phone_number': reg_form.cleaned_data['phone_number'],
        'persona': persona,
        'persona_other': persona_other,
        'project_name': reg_form.cleaned_data['project_name'],
        'atypical_user': reg_form.cleaned_data.get('atypical_user'),
        'additional_hubspot_data': additional_hubspot_data,
    }


def get_new_sso_user_data_from_session(request):
    """
    Fetches data related to the a new user that is registering and logging on
    using sso (if that data is available).
    :param request: HttpRequest
    :return: dict or None
    """
    return request.session.get('ssoNewUserData', {})


def get_new_sso_user_project_name_from_session(request):
    """
    This gets the project name from sso user data stored in the session.
    :param request: HttpRequest
    :return: String (project name) or None
    """
    return request.session.get('ssoNewUserData', {}).get('project_name')


def clear_sso_registration_data_from_session(request):
    """
    Clears up any registration / invitation related data from the request's
    session.
    :param request: HttpRequest
    """
    if 'ssoNewUserData' in request.session:
        del request.session['ssoNewUserData']
    if 'ssoNewUsername' in request.session:
        del request.session['ssoNewUsername']
    if 'ssoInvitation' in request.session:
        del request.session['ssoInvitation']
