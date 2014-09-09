from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_noop
from corehq.apps.custom_data_fields.views import CustomDataFieldsMixin

from corehq.apps.users.decorators import require_can_edit_commcare_users
from corehq.apps.users.views import BaseUserSettingsView


class UserFieldsView(CustomDataFieldsMixin, BaseUserSettingsView):
    urlname = "user_fields_view"
    page_name = ugettext_noop("Edit User Fields")
    field_type = 'UserFields'
    form_label = 'User Fields'

    @method_decorator(require_can_edit_commcare_users)
    def dispatch(self, request, *args, **kwargs):
        return super(UserFieldsView, self).dispatch(request, *args, **kwargs)
