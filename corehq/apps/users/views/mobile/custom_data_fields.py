from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _

from corehq.apps.custom_data_fields.views import CustomDataFieldsMixin
from corehq.apps.users.decorators import require_can_edit_commcare_users
from corehq.apps.users.views import BaseUserSettingsView


class UserFieldsView(CustomDataFieldsMixin, BaseUserSettingsView):
    urlname = 'user_fields_view'
    field_type = 'UserFields'
    entity_string = _("User")

    @method_decorator(require_can_edit_commcare_users)
    def dispatch(self, request, *args, **kwargs):
        return super(UserFieldsView, self).dispatch(request, *args, **kwargs)
