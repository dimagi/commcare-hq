from memoized import memoized

from django.utils.translation import gettext as _

from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition
from corehq.apps.reports.util import get_allowed_tableau_groups_for_domain
from corehq.apps.user_importer.importer import SiteCodeToLocationCache
from corehq.apps.user_importer.validation import (
    RoleValidator,
    ProfileValidator,
    LocationValidator,
    TableauGroupsValidator,
    TableauRoleValidator,
    CustomDataValidator,
    EmailValidator,
    UserAccessValidator,
)
from corehq.apps.users.validation import validate_primary_location_assignment
from corehq.apps.registration.validation import AdminInvitesUserFormValidator


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
            (self.validate_email, [data.get("email"), is_post]),
            (self.validate_locations, [data.get("username"), data.get("assigned_locations"),
                                       data.get("primary_location")]),
            (self.validate_user_access, [data.get("username")]),
            (self.validate_tableau_group, [data.get("tableau_groups", None)]),
            (self.validate_tableau_role, [data.get("tableau_role")]),
        ]

        for validator, args in validators:
            error = validator(*args)
            if error:
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

    @property
    def location_cache(self):
        return SiteCodeToLocationCache(self.domain)

    def validate_parameters(self, parameters, is_post):
        allowed_params = ['role', 'primary_location', 'assigned_locations',
                          'profile', 'custom_user_data', 'tableau_role', 'tableau_groups']
        if is_post:
            allowed_params.append('email')
        invalid_params = [param for param in parameters if param not in allowed_params]
        if invalid_params:
            return f"Invalid parameter(s): {', '.join(invalid_params)}"
        return AdminInvitesUserFormValidator.validate_parameters(self.domain, self.requesting_user, parameters)

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

    def validate_email(self, email, is_post):
        if is_post and email is not None:
            error = AdminInvitesUserFormValidator.validate_email(self.domain, email)
            if error:
                return error
        email_validator = EmailValidator(self.domain, 'email')
        spec = {'email': email}
        return email_validator.validate_spec(spec)

    def validate_locations(self, editable_user, assigned_location_codes, primary_location_code):
        if assigned_location_codes is None and primary_location_code is None:
            return
        if ((assigned_location_codes is not None and primary_location_code is None)
                or (assigned_location_codes is None and primary_location_code is not None)):
            return _('Both primary_location and locations must be provided together.')

        error = validate_primary_location_assignment(primary_location_code, assigned_location_codes)
        if error:
            return error

        location_validator = LocationValidator(self.domain, self.requesting_user, self.location_cache, True)
        spec = {'location_code': assigned_location_codes,
                'username': editable_user}
        return location_validator.validate_spec(spec)

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
