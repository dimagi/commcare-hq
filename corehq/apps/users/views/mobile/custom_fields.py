import json

from django.contrib import messages
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _, ugettext_noop
from django import forms

from crispy_forms.bootstrap import InlineField, FormActions, StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy

from corehq.apps.custom_fields.views import CustomFieldsMixin

from corehq.apps.users.decorators import require_can_edit_commcare_users
from corehq.apps.users.views import BaseUserSettingsView


class UserFieldsView(CustomFieldsMixin, BaseUserSettingsView):
    urlname = "user_fields_view"
    page_name = ugettext_noop("Edit User Fields")


    @method_decorator(require_can_edit_commcare_users)
    def dispatch(self, request, *args, **kwargs):
        return super(UserFieldsView, self).dispatch(request, *args, **kwargs)

    # def post(self, request, *args, **kwargs):
        # self.save_custom_fields(self.request.POST.get('customFields', u'[]'))
        # return self.get(request, success=True, *args, **kwargs)

    # def post(self, request, *args, **kwargs):
        # form = self.form_class(data=self.request.POST)
        # if form.is_valid():
            # print "valid form!!"
        # else:
            # print "invalid form :("
        # messages.success(self.request, _('Fields added successfully'))
        # return self.get(request, *args, **kwargs)
