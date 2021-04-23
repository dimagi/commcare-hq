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
