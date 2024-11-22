from memoized import memoized

from corehq.apps.user_importer.validation import RoleValidator
from corehq.apps.user_importer.validation import ProfileValidator

from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition


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

    def validate_role(self, role):
        spec = {'role': role}
        return RoleValidator(self.domain, self.roles_by_name()).validate_spec(spec)

    def validate_profile(self, new_profile_name):
        profile_validator = ProfileValidator(self.domain, self.upload_user, True, self.profiles_by_name())
        spec = {'user_profile': new_profile_name}
        return profile_validator.validate_spec(spec)
