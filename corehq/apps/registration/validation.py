from memoized import memoized

from django.utils.translation import gettext_lazy as _

from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition
from corehq.apps.user_importer.validation import (
    RoleValidator,
    ProfileValidator,
    EmailValidator
)
from corehq.apps.users.models import Invitation, WebUser
from corehq.toggles import TABLEAU_USER_SYNCING


class AdminInvitesUserValidator():
    def __init__(self, domain, upload_user):
        self.domain = domain
        self.upload_user = upload_user

    @property
    @memoized
    def roles_by_name(self):
        from corehq.apps.users.views.utils import get_editable_role_choices
        return {role[1]: role[0] for role in get_editable_role_choices(self.domain, self.upload_user,
                                                  allow_admin_role=True)}

    @property
    @memoized
    def profiles_by_name(self):
        from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView
        definition = CustomDataFieldsDefinition.get(self.domain, UserFieldsView.field_type)
        if definition:
            profiles = definition.get_profiles()
            return {
                profile.name: profile
                for profile in profiles
            }
        else:
            return {}

    @property
    @memoized
    def current_users_and_pending_invites(self):
        current_users = [user.username.lower() for user in WebUser.by_domain(self.domain)]
        pending_invites = [di.email.lower() for di in Invitation.by_domain(self.domain)]
        return current_users + pending_invites

    def validate_parameters(self, parameters):
        can_edit_tableau_config = (self.upload_user.has_permission(self.domain, 'edit_user_tableau_config')
                        and TABLEAU_USER_SYNCING.enabled(self.domain))
        if (('tableau_role' in parameters or 'tableau_group_indices' in parameters)
        and not can_edit_tableau_config):
            return _("You do not have permission to edit Tableau Configuraion.")

        has_profile_privilege = domain_has_privilege(self.domain, privileges.APP_USER_PROFILES)
        if 'profile' in parameters and not has_profile_privilege:
            return _("This domain does not have user profile privileges.")

    def validate_role(self, role):
        spec = {'role': role}
        return RoleValidator(self.domain, self.roles_by_name()).validate_spec(spec)

    def validate_profile(self, new_profile_name):
        profile_validator = ProfileValidator(self.domain, self.upload_user, True, self.profiles_by_name())
        spec = {'user_profile': new_profile_name}
        return profile_validator.validate_spec(spec)

    def validate_email(self, email, is_post):
        if is_post:
            if email.lower() in self.current_users_and_pending_invites:
                return _("A user with this email address is already in "
                        "this project or has a pending invitation.")
            web_user = WebUser.get_by_username(email)
            if web_user and not web_user.is_active:
                return _("A user with this email address is deactivated. ")

        email_validator = EmailValidator(self.domain, 'email')
        spec = {'email': email}
        return email_validator.validate_spec(spec)
