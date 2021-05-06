from django.conf import settings
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.utils.translation import ugettext as _

from dimagi.utils.web import get_ip

from corehq.apps.analytics.tasks import (
    track_workflow,
    track_web_user_registration_hubspot,
    send_hubspot_form,
    HUBSPOT_NEW_USER_INVITE_FORM,
)
from corehq.apps.registration.utils import activate_new_user
from corehq.apps.sso.models import IdentityProvider, AuthenticatedEmailDomain
from corehq.apps.sso.utils.session_helpers import (
    get_sso_invitation_from_session,
    get_sso_user_first_name_from_session,
    get_sso_user_last_name_from_session,
    get_new_sso_user_data_from_session,
)
from corehq.apps.sso.utils.user_helpers import get_email_domain_from_username
from corehq.apps.users.models import CouchUser, WebUser
from corehq.const import (
    USER_CHANGE_VIA_SSO_INVITE,
    USER_CHANGE_VIA_SSO_NEW_USER,
)


class SsoBackend(ModelBackend):
    """
    Authenticates against an IdentityProvider and SAML2 session data.
    """

    def authenticate(self, request, username, idp_slug, is_handshake_successful):
        if not (request and username and idp_slug and is_handshake_successful):
            return None

        try:
            identity_provider = IdentityProvider.objects.get(slug=idp_slug)
        except IdentityProvider.DoesNotExist:
            # not sure how we would even get here, but just in case
            request.sso_login_error = f"Identity Provider {idp_slug} does not exist."
            return None

        if not identity_provider.is_active:
            request.sso_login_error = f"This Identity Provider {idp_slug} is not active."
            return None

        email_domain = get_email_domain_from_username(username)
        if not email_domain:
            # not a valid username
            request.sso_login_error = f"Username {username} is not valid."
            return None

        if not AuthenticatedEmailDomain.objects.filter(
            email_domain=email_domain, identity_provider=identity_provider
        ).exists():
            # if this user's email domain is not authorized by this identity
            # do not continue with authentication
            request.sso_login_error = (
                f"The Email Domain {email_domain} is not allowed to "
                f"authenticate with this Identity Provider ({idp_slug})."
            )
            return None

        invitation = get_sso_invitation_from_session(request)

        # because the django messages middleware is not yet available...
        request.sso_new_user_messages = {
            'success': [],
            'error': [],
        }

        try:
            user = User.objects.get(username=username)
            is_new_user = False
            web_user = WebUser.get_by_username(username)
        except User.DoesNotExist:
            user, web_user = self._create_new_user(request, username, invitation)
            is_new_user = True

        if invitation:
            self._process_invitation(request, invitation, web_user, is_new_user)

        request.sso_login_error = None
        return user

    def _create_new_user(self, request, username, invitation):
        """
        This creates a new user in HQ based on information in the request.
        :param request: HttpRequest
        :param username: String (username)
        :param invitation: Invitation
        :return: User, WebUser
        """
        created_via = (USER_CHANGE_VIA_SSO_INVITE if invitation
                       else USER_CHANGE_VIA_SSO_NEW_USER)
        created_by = (CouchUser.get_by_user_id(invitation.invited_by) if invitation
                      else None)
        domain = invitation.domain if invitation else None

        new_web_user = activate_new_user(
            username=username,
            password=User.objects.make_random_password(),
            created_by=created_by,
            created_via=created_via,
            first_name=get_sso_user_first_name_from_session(request),
            last_name=get_sso_user_last_name_from_session(request),
            domain=domain,
            ip=get_ip(request),
        )
        request.sso_new_user_messages['success'].append(
            _("User account for {} created.").format(new_web_user.username)
        )
        self._process_new_user_data(request, new_web_user)
        return User.objects.get(username=username), new_web_user

    @staticmethod
    def _process_new_user_data(request, new_web_user):
        """
        If available, this makes sure we apply any relevant user data
        :param request: HttpRequest
        :param new_web_user: WebUser
        :return:
        """
        user_data = get_new_sso_user_data_from_session(request)
        if not user_data:
            return

        phone_number = user_data['phone_number']
        if phone_number:
            new_web_user.phone_numbers.append(phone_number)
            new_web_user.save()

        if settings.IS_SAAS_ENVIRONMENT:
            track_workflow(
                new_web_user.username,
                "Requested New Account via SSO",
                {
                    'environment': settings.SERVER_ENVIRONMENT,
                }
            )
            track_workflow(
                new_web_user.username,
                "Persona Field Filled Out via SSO",
                {
                    'personachoice': user_data['persona'],
                    'personaother': user_data['persona_other'],
                }
            )
            track_web_user_registration_hubspot(
                request,
                new_web_user,
                user_data['additional_hubspot_data'],
            )

    @staticmethod
    def _process_invitation(request, invitation, web_user, is_new_user=False):
        """
        Processes the Invitation (if available) and sets up the user in the
        new domain they were invited to.
        :param request: HttpRequest
        :param invitation: Invitation or None
        :param web_user: WebUser
        """
        request.sso_invitation_status = {}
        if invitation.is_expired:
            request.sso_new_user_messages['error'].append(
                _("Could not accept invitation because it is expired.")
            )
            return

        invitation.accept_invitation_and_join_domain(web_user)
        request.sso_new_user_messages['success'].append(
            _('You have been added to the "{}" project space.').format(
                invitation.domain,
            )
        )

        if settings.IS_SAAS_ENVIRONMENT and is_new_user:
            track_workflow(
                web_user.username,
                "New User Accepted a project invitation with SSO",
                {"New User Accepted a project invitation": "yes"}
            )
            send_hubspot_form(
                HUBSPOT_NEW_USER_INVITE_FORM,
                request,
                user=web_user
            )
