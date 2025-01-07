from memoized import memoized

from django.utils.translation import gettext as _

from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.custom_data_fields.models import (
    CustomDataFieldsDefinition,
    PROFILE_SLUG,
)
from corehq.apps.reports.util import get_allowed_tableau_groups_for_domain
from corehq.apps.users.models import CouchUser, Invitation
from corehq.apps.user_importer.validation import (
    RoleValidator,
    ProfileValidator,
    LocationValidator,
    TableauGroupsValidator,
    TableauRoleValidator,
    CustomDataValidator,
    EmailValidator,
    UserAccessValidator,
    UserRetrievalResult,
)
from corehq.apps.users.validation import validate_primary_location_assignment
from corehq.apps.registration.validation import AdminInvitesUserFormValidator
from corehq.toggles import TABLEAU_USER_SYNCING


class WebUserResourceValidator():
    def __init__(self, domain, requesting_user):
        self.domain = domain
        self.requesting_user = requesting_user

    def is_valid(self, data, is_post):
        errors = []

        validators = [
            (self.validate_parameters, [data.keys(), is_post]),
            (self.validate_required_fields, [data, is_post]),
            (self.validate_role, [data.get("role")]),
            (self.validate_profile, [data.get("profile"), is_post]),
            (self.validate_custom_data, [data.get("custom_user_data"), data.get("profile")]),
            (self.validate_custom_data_with_profile, [data.get("custom_user_data"), data.get("profile")]),
            (self.validate_email, [data.get("email"), is_post]),
            (self.validate_locations, [data.get("email"), data.get("assigned_location_ids"),
                                       data.get("primary_location_id")]),
            (self.validate_user_access, [data.get("email")]),
            (self.validate_tableau_group, [data.get("tableau_groups", None)]),
            (self.validate_tableau_role, [data.get("tableau_role")]),
        ]

        for validator, args in validators:
            error = validator(*args)
            if isinstance(error, list):
                errors += error
            elif error:
                errors.append(error)

        return errors

    @property
    def roles_by_name(self):
        from corehq.apps.users.views.utils import get_editable_role_choices
        return {role[1]: role[0] for role in get_editable_role_choices(self.domain, self.requesting_user,
                                                  allow_admin_role=True)}

    @property
    @memoized
    def profiles_by_name(self):
        from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView
        return CustomDataFieldsDefinition.get_profiles_by_name(self.domain, UserFieldsView.field_type)

    def validate_parameters(self, parameters, is_post):
        errors = []
        allowed_params = ['role', 'primary_location_id', 'assigned_location_ids',
                          'profile', 'custom_user_data', 'tableau_role', 'tableau_groups']
        if is_post:
            allowed_params.append('email')
        invalid_params = [param for param in parameters if param not in allowed_params]
        if invalid_params:
            errors.append(f"Invalid parameter(s): {', '.join(invalid_params)}")

        if 'tableau_role' in parameters or 'tableau_groups' in parameters:
            can_edit_tableau_config = (
                self.requesting_user.has_permission(self.domain, 'edit_user_tableau_config')
                and TABLEAU_USER_SYNCING.enabled(self.domain)
            )
            if not can_edit_tableau_config:
                errors.append(_("You do not have permission to edit Tableau Configuration."))

        if 'profile' in parameters and not domain_has_privilege(self.domain, privileges.APP_USER_PROFILES):
            errors.append(_("This domain does not have user profile privileges."))

        if (('primary_location_id' in parameters or 'assigned_location_ids' in parameters)
           and not domain_has_privilege(self.domain, privileges.LOCATIONS)):
            errors.append(_("This domain does not have locations privileges."))

        return errors

    def validate_required_fields(self, spec, is_post):
        email = spec.get('email')
        role = spec.get('role')
        if is_post:
            if not email or not role:
                return _("'email' and 'role' are required for each user")
        else:
            if role == '':
                return _("'role' is required for each user")

    def validate_role(self, role):
        spec = {'role': role}
        return RoleValidator(self.domain, self.roles_by_name).validate_spec(spec)

    def validate_profile(self, new_profile_name, is_post):
        if not is_post and new_profile_name is None:
            return None
        profile_validator = ProfileValidator(self.domain, self.requesting_user, True, self.profiles_by_name)
        spec = {'user_profile': new_profile_name}
        return profile_validator.validate_spec(spec)

    def validate_custom_data(self, custom_data, profile_name):
        custom_data_validator = CustomDataValidator(self.domain, self.profiles_by_name, True)
        spec = {'data': custom_data, 'user_profile': profile_name}
        return custom_data_validator.validate_spec(spec)

    def validate_custom_data_with_profile(self, custom_data, profile_name):
        if custom_data is None or profile_name is None:
            return

        errors = []
        profile = self.profiles_by_name.get(profile_name)

        system_fields = set(profile.fields.keys()) if profile else set()
        system_fields.add(PROFILE_SLUG)

        for key in custom_data.keys():
            if key in system_fields:
                errors.append(_("'{}' cannot be set directly").format(key))
        return errors

    def validate_email(self, email, is_post):
        if is_post and email is not None:
            error = AdminInvitesUserFormValidator.validate_email(self.domain, email)
            if error:
                return error
        email_validator = EmailValidator(self.domain, 'email')
        spec = {'email': email}
        return email_validator.validate_spec(spec)

    def validate_locations(self, editable_user, assigned_location_ids, primary_location_id):
        if assigned_location_ids is None and primary_location_id is None:
            return
        if ((assigned_location_ids is not None and primary_location_id is None)
                or (assigned_location_ids is None and primary_location_id is not None)):
            return _('Both primary_location and locations must be provided together.')

        error = validate_primary_location_assignment(primary_location_id, assigned_location_ids)
        if error:
            return error
        location_validator = LocationValidator(self.domain, self.requesting_user, None, True)
        user_result = self._get_invitation_or_editable_user(editable_user, self.domain)
        return location_validator.validate_location_ids(user_result, assigned_location_ids)

    def validate_user_access(self, editable_user):
        user_access_validator = UserAccessValidator(self.domain, self.requesting_user, True)
        spec = {'username': editable_user}
        return user_access_validator.validate_spec(spec)

    def validate_tableau_group(self, tableau_groups):
        if tableau_groups is None:
            return
        allowed_groups_for_domain = get_allowed_tableau_groups_for_domain(self.domain) or []
        return TableauGroupsValidator.validate_tableau_groups(allowed_groups_for_domain, tableau_groups)

    def validate_tableau_role(self, tableau_role):
        if tableau_role is None:
            return
        return TableauRoleValidator.validate_tableau_role(tableau_role)

    def _get_invitation_or_editable_user(self, username_or_email, domain) -> UserRetrievalResult:
        editable_user = None
        try:
            invitation = Invitation.objects.get(domain=domain, email=username_or_email, is_accepted=False)
            return UserRetrievalResult(invitation=invitation)
        except Invitation.DoesNotExist:
            editable_user = CouchUser.get_by_username(username_or_email, strict=True)
        return UserRetrievalResult(editable_user=editable_user)
