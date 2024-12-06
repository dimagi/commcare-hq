from django.utils.translation import gettext_lazy as _

from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.users.models import WebUser, Invitation
from corehq.toggles import TABLEAU_USER_SYNCING


class AdminInvitesUserFormValidator():

    @staticmethod
    def validate_parameters(domain, upload_user, parameters):
        if 'tableau_role' in parameters or 'tableau_group_indices' in parameters:
            can_edit_tableau_config = (
                upload_user.has_permission(domain, 'edit_user_tableau_config')
                and TABLEAU_USER_SYNCING.enabled(domain)
            )
            if not can_edit_tableau_config:
                return _("You do not have permission to edit Tableau Configuration.")

        if 'profile' in parameters and not domain_has_privilege(domain, privileges.APP_USER_PROFILES):
            return _("This domain does not have user profile privileges.")

        if (('primary_location' in parameters or 'assigned_locations' in parameters)
           and not domain_has_privilege(domain, privileges.LOCATIONS)):
            return _("This domain does not have locations privileges.")

    @staticmethod
    def validate_email(domain, email):
        current_users = [user.username.lower() for user in WebUser.by_domain(domain)]
        pending_invites = [di.email.lower() for di in Invitation.by_domain(domain)]
        current_users_and_pending_invites = current_users + pending_invites

        if email.lower() in current_users_and_pending_invites:
            return _("A user with this email address is already in "
                    "this project or has a pending invitation.")
        web_user = WebUser.get_by_username(email)
        if web_user and not web_user.is_active:
            return _("A user with this email address is deactivated. ")
