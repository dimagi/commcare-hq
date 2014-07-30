import json

from django.contrib import messages
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _, ugettext_noop
from django import forms

from crispy_forms.bootstrap import InlineField, FormActions, StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy

from corehq.apps.users.decorators import require_can_edit_commcare_users
from corehq.apps.users.views import BaseUserSettingsView


class UserFieldsForm(forms.Form):
    name = forms.CharField(label="Field Name")
    is_required = forms.BooleanField(label="Required")

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_id = 'user-fields-form'
        # self.helper.form_class = 'form-horizontal'
        self.helper.form_method = 'post'
        # self.helper.template = 'bootstrap/table_inline_formset.html'
        # crispy_forms/templates/bootstrap/table_inline_formset.html
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                UserFieldsView.page_name,
                crispy.Fieldset(
                    crispy.Row(
                        crispy.HTML('<span class="sortable-handle">'
                                      '<i class="icon-resize-vertical"></i>'
                                    '</span>'),
                        crispy.Field('name', data_bind='value: name'),
                        crispy.Field('is_required', data_bind='checked: isRequired'),
                        css_class="form-inline",
                    ),
                    data_bind="sortable: customFields",
                    css_class="controls-row",
                ),
            ),
                    # <td>
                        # <select data-bind="
                            # options: $root.available_versions,
                            # value: version
                        # ">
                        # </select>
                    # </td>
                    # <td>
                        # <input type="text" data-bind="value: label">
                    # </td>
                    # <td>
                        # <input type="checkbox" value="superuser-only" data-bind="checked: superuser_only" />
                    # </td>
                    # <td>
                        # <button type="button" class="close" data-bind="click: $root.removeVersion">&times;</button>
                    # </td>
            FormActions(crispy.ButtonHolder(crispy.Submit('save', 'Save Fields',
                css_id='save-user-fields')))
        )
        super(UserFieldsForm, self).__init__(*args, **kwargs)


class UserFieldsView(BaseUserSettingsView):
    urlname = "user_fields_view"
    template_name = "users/user_fields.html"
    # form_class = UserFieldsForm
    page_name = ugettext_noop("Edit User Fields")

    @method_decorator(require_can_edit_commcare_users)
    def dispatch(self, request, *args, **kwargs):
        return super(UserFieldsView, self).dispatch(request, *args, **kwargs)

    def get_custom_fields(self):
        # TODO load me from db
        return [
            {"slug": "dob", "label": "DOB", "isRequired": True},
            {"slug": "gender", "label": "Gender", "isRequired": False},
        ]

    def save_custom_fields(self, fields):
        # TODO actually save me
        print json.loads(fields)

    @property
    def page_context(self):
        return {
            # "user_fields_form": self.form_class(),
            "custom_fields": self.get_custom_fields(),
        }

    def post(self, request, *args, **kwargs):
        self.save_custom_fields(self.request.POST.get('customFields', u'[]'))
        return self.get(request, success=True, *args, **kwargs)

    # def post(self, request, *args, **kwargs):
        # form = self.form_class(data=self.request.POST)
        # if form.is_valid():
            # print "valid form!!"
        # else:
            # print "invalid form :("
        # messages.success(self.request, _('Fields added successfully'))
        # return self.get(request, *args, **kwargs)
