from __future__ import absolute_import
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _

from corehq.apps.custom_data_fields import CustomDataModelMixin
from corehq.apps.users.decorators import require_can_edit_commcare_users
from corehq.apps.users.tasks import remove_unused_custom_fields_from_users_task
from corehq.apps.users.views import BaseUserSettingsView

CUSTOM_USER_DATA_FIELD_TYPE = 'UserFields'


class UserFieldsView(CustomDataModelMixin, BaseUserSettingsView):
    urlname = 'user_fields_view'
    field_type = CUSTOM_USER_DATA_FIELD_TYPE
    entity_string = _("User")
    show_purge_existing = True

    @method_decorator(require_can_edit_commcare_users)
    def dispatch(self, request, *args, **kwargs):
        return super(UserFieldsView, self).dispatch(request, *args, **kwargs)

    def update_existing_models(self):
        remove_unused_custom_fields_from_users_task.delay(self.domain)
