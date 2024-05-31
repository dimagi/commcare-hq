from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _

from corehq.apps.custom_data_fields.edit_model import CustomDataModelMixin
from corehq.apps.custom_data_fields.models import CustomDataFieldsProfile
from corehq.apps.users.decorators import require_can_edit_commcare_users, get_permission_name
from corehq.apps.users.models import HqPermissions
from corehq.apps.users.tasks import remove_unused_custom_fields_from_users_task
from corehq.apps.users.views import BaseUserSettingsView

CUSTOM_USER_DATA_FIELD_TYPE = 'UserFields'


class UserFieldsView(CustomDataModelMixin, BaseUserSettingsView):
    urlname = 'user_fields_view'
    field_type = CUSTOM_USER_DATA_FIELD_TYPE
    entity_string = _("User")
    show_purge_existing = True
    _show_profiles = True
    page_title = _('Edit User Fields')

    @method_decorator(require_can_edit_commcare_users)
    def dispatch(self, request, *args, **kwargs):
        return super(UserFieldsView, self).dispatch(request, *args, **kwargs)

    def update_existing_models(self):
        remove_unused_custom_fields_from_users_task.delay(self.domain)

    @classmethod
    def get_user_accessible_profiles(cls, domain, couch_user):
        all_profiles = cls.get_definition_for_domain(domain).get_profiles()
        if couch_user.has_permission(domain, get_permission_name(HqPermissions.edit_user_profile)):
            return all_profiles

        role = couch_user.get_role(domain)
        permission = role.permissions if role else HqPermissions()
        accessible_profile_ids = permission.edit_user_profile_list
        accessible_profiles = {p for p in all_profiles if str(p.id) in accessible_profile_ids}
        return accessible_profiles

    @classmethod
    def get_displayable_profiles_and_edit_permission(cls, current_profile_id, domain, couch_user):
        can_edit_current_profile = True

        if current_profile_id:
            can_edit_current_profile = couch_user.has_permission(
                domain,
                get_permission_name(HqPermissions.access_profile),
                data=str(current_profile_id)
            )

        if can_edit_current_profile:
            profiles = cls.get_user_accessible_profiles(domain, couch_user)
        else:
            profiles = {CustomDataFieldsProfile.objects.get(id=current_profile_id)}
        return profiles, can_edit_current_profile
