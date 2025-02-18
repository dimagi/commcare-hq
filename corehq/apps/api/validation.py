
from attrs import define, field
from typing import List

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


class WebUserValidationException(Exception):
    def __init__(self, message):
        self.message = message if isinstance(message, list) else [message]


@define
class WebUserResourceSpec:
    domain: str = field()
    requesting_user = field()
    email: str = field()
    is_post: bool = field(default=False)
    role: str = field(default=None)
    primary_location_id: str = field(default=None)
    assigned_location_ids: List[str] = field(default=None)
    new_or_existing_profile_name: str = field(default=None)
    new_or_existing_user_data: dict = field(default={})
    tableau_role: str = field(default=None)
    tableau_groups: List[str] = field(default=None)
    parameters: List[str] = field(default=[])

    _profiles_by_name_cache: dict = field(default=None)

    @property
    def roles_by_name(self):
        from corehq.apps.users.views.utils import get_editable_role_choices
        return {role[1]: role[0] for role in get_editable_role_choices(self.domain, self.requesting_user,
                                                  allow_admin_role=True)}

    @property
    def profiles_by_name(self):
        if not self._profiles_by_name_cache:
            from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView
            self._profiles_by_name_cache = (
                CustomDataFieldsDefinition.get_profiles_by_name(self.domain, UserFieldsView.field_type)
            )
        return self._profiles_by_name_cache

    @email.validator
    def validate_user_access(self, attribute, email):
        user_access_validator = UserAccessValidator(self.domain, self.requesting_user, True)
        spec = {'username': email}
        return user_access_validator.validate_spec(spec)

    @email.validator
    def validate_email(self, attribute, email):
        if self.is_post and email is not None:
            error = AdminInvitesUserFormValidator.validate_email(self.domain, email)
            if error:
                raise WebUserValidationException(error)
        email_validator = EmailValidator(self.domain, 'email')
        spec = {'email': email}
        error = email_validator.validate_spec(spec)
        if error:
            raise WebUserValidationException(error)

    @email.validator
    def validate_required_email(self, attribute, email):
        if self.is_post and not email:
            raise WebUserValidationException(_("'email' is required for each user"))

    @role.validator
    def validate_required_role(self, attribute, role):
        if self.is_post and not role:
            raise WebUserValidationException(_("'role' required for each user"))
        elif role == '':
            raise WebUserValidationException(_("'role' is required for each user"))

    @role.validator
    def validate_role(self, attribute, role):
        spec = {'role': role}
        error = RoleValidator(self.domain, self.roles_by_name).validate_spec(spec)
        if error:
            raise WebUserValidationException(error)

    @primary_location_id.validator
    def validate_locations(self, attribute, primary_location_id):
        self._validate_locations(self.assigned_location_ids, primary_location_id)

    @assigned_location_ids.validator
    def validate_assigned_locations(self, attribute, assigned_location_ids):
        if assigned_location_ids is None:
            return
        self._validate_locations(assigned_location_ids, self.primary_location_id)
        location_validator = LocationValidator(self.domain, self.requesting_user, None, True)
        user_result = self._get_invitation_or_editable_user(self.email, self.domain)
        error = location_validator.validate_location_ids(user_result, assigned_location_ids)
        if error:
            raise WebUserValidationException(error)

    def _validate_locations(self, assigned_location_ids, primary_location_id):
        if assigned_location_ids is None and primary_location_id is None:
            return
        if ((assigned_location_ids is not None and primary_location_id is None)
                or (assigned_location_ids is None and primary_location_id is not None)):
            raise WebUserValidationException(_('Both primary_location and locations must be provided together.'))

        error = validate_primary_location_assignment(primary_location_id, assigned_location_ids)
        if error:
            raise WebUserValidationException(error)

    @new_or_existing_profile_name.validator
    def validate_profile(self, attribute, new_or_existing_profile_name):
        self._validate_custom_data_against_profile(self.new_or_existing_user_data, new_or_existing_profile_name)

        profile_validator = ProfileValidator(self.domain, self.requesting_user, True, self.profiles_by_name)
        spec = {'user_profile': new_or_existing_profile_name}
        error = profile_validator.validate_spec(spec)
        if error:
            raise WebUserValidationException(error)

    @new_or_existing_user_data.validator
    def validate_custom_data(self, attribute, new_or_existing_user_data):
        self._validate_custom_data_against_profile(new_or_existing_user_data, self.new_or_existing_profile_name)

        custom_data_validator = CustomDataValidator(self.domain, self.profiles_by_name, True)
        spec = {'data': new_or_existing_user_data, 'user_profile': self.new_or_existing_profile_name}
        error = custom_data_validator.validate_spec(spec)
        if error:
            raise WebUserValidationException(error)

    def _validate_custom_data_against_profile(self, new_or_existing_user_data, new_or_existing_profile_name):
        errors = []
        profile = self.profiles_by_name.get(new_or_existing_profile_name)
        system_fields = set(profile.fields.keys()) if profile else set()
        system_fields.add(PROFILE_SLUG)
        for key, value in new_or_existing_user_data.items():
            if key in system_fields:
                if value == profile.fields.get(key, object()):
                    continue
                errors.append(_("'{}' is defined by the profile so cannot be set directly").format(key))
        if errors:
            raise WebUserValidationException(errors)

    @tableau_role.validator
    def validate_tableau_role(self, attribute, value):
        if value is None:
            return
        error = TableauRoleValidator.validate_tableau_role(value)
        if error:
            raise WebUserValidationException(error)

    @tableau_groups.validator
    def validate_tableau_group(self, attribute, tableau_groups):
        if tableau_groups is None:
            return
        allowed_groups_for_domain = get_allowed_tableau_groups_for_domain(self.domain) or []
        error = TableauGroupsValidator.validate_tableau_groups(allowed_groups_for_domain, tableau_groups)
        if error:
            raise WebUserValidationException(error)

    @parameters.validator
    def validate_parameters(self, attribute, parameters):
        allowed_params = ['role', 'primary_location_id', 'assigned_location_ids',
                          'profile', 'user_data', 'tableau_role', 'tableau_groups']
        errors = []
        if self.is_post:
            allowed_params.append('email')
        invalid_params = [param for param in parameters if param not in allowed_params]
        if invalid_params:
            errors.append(_(f"Invalid parameter(s): {', '.join(invalid_params)}"))
        errors.extend(self._validate_param_permissions(parameters))
        if errors:
            raise WebUserValidationException(errors)

    def _validate_param_permissions(self, parameters):
        errors = []
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

    def _get_invitation_or_editable_user(self, username_or_email, domain) -> UserRetrievalResult:
        editable_user = None
        try:
            invitation = Invitation.objects.get(domain=domain, email=username_or_email, is_accepted=False)
            return UserRetrievalResult(invitation=invitation)
        except Invitation.DoesNotExist:
            editable_user = CouchUser.get_by_username(username_or_email, strict=True)
        return UserRetrievalResult(editable_user=editable_user)
