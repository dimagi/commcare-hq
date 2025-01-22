from memoized import memoized

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
)
from corehq.apps.users.validation import validate_primary_location_assignment
from corehq.apps.registration.validation import AdminInvitesUserFormValidator


class WebUserResourceValidator():
    def __init__(self, domain, requesting_user):
        self.domain = domain
        self.requesting_user = requesting_user

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

    def validate_parameters(self, parameters):
        allowed_params = ['email', 'role', 'primary_location', 'assigned_locations',
                          'profile', 'custom_user_data', 'tableau_role', 'tableau_groups']
        invalid_params = [param for param in parameters if param not in allowed_params]
        if invalid_params:
            return f"Invalid parameter(s): {', '.join(invalid_params)}"
        return AdminInvitesUserFormValidator.validate_parameters(self.domain, self.requesting_user, parameters)

    def validate_role(self, role):
        spec = {'role': role}
        return RoleValidator(self.domain, self.roles_by_name()).validate_spec(spec)

    def validate_profile(self, new_profile_name):
        profile_validator = ProfileValidator(self.domain, self.requesting_user, True, self.profiles_by_name())
        spec = {'user_profile': new_profile_name}
        return profile_validator.validate_spec(spec)

    def validate_custom_data(self, custom_data, profile_name):
        custom_data_validator = CustomDataValidator(self.domain, self.profiles_by_name())
        spec = {'data': custom_data, 'user_profile': profile_name}
        return custom_data_validator.validate_spec(spec)

    def validate_email(self, email, is_post):
        if is_post:
            error = AdminInvitesUserFormValidator.validate_email(self.domain, email)
            if error:
                return error
        email_validator = EmailValidator(self.domain, 'email')
        spec = {'email': email}
        return email_validator.validate_spec(spec)

    def validate_locations(self, editable_user, assigned_location_codes, primary_location_code):
        error = validate_primary_location_assignment(primary_location_code, assigned_location_codes)
        if error:
            return error

        location_validator = LocationValidator(self.domain, self.requesting_user, self.location_cache, True)
        location_codes = list(set(assigned_location_codes + [primary_location_code]))
        spec = {'location_code': location_codes,
                'username': editable_user}
        return location_validator.validate_spec(spec)

    def validate_tableau_group(self, tableau_groups):
        allowed_groups_for_domain = get_allowed_tableau_groups_for_domain(self.domain) or []
        return TableauGroupsValidator.validate_tableau_groups(allowed_groups_for_domain, tableau_groups)

    def validate_tableau_role(self, tableau_role):
        return TableauRoleValidator.validate_tableau_role(tableau_role)
