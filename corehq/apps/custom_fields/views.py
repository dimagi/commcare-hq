import json

from django.contrib import messages
from django.utils.translation import ugettext as _, ugettext_noop
from django import forms

from crispy_forms.bootstrap import InlineField, FormActions, StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy

from .models import CustomFieldsDefinition, CustomField


class CustomFieldsForm(forms.Form):
    name = forms.CharField(label="Field Name")
    is_required = forms.BooleanField(label="Required")

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_id = 'custom-fields-form'
        # self.helper.form_class = 'form-horizontal'
        self.helper.form_method = 'post'
        # self.helper.template = 'bootstrap/table_inline_formset.html'
        # crispy_forms/templates/bootstrap/table_inline_formset.html
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                CustomFieldsView.page_name,
                crispy.Fieldset(
                    crispy.Row(
                        crispy.HTML('<span class="sortable-handle">'
                                      '<i class="icon-resize-vertical"></i>'
                                    '</span>'),
                        crispy.Field('name', data_bind='value: name'),
                        crispy.Field('is_required', data_bind='checked: is_required'),
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
                css_id='save-custom-fields')))
        )
        super(CustomFieldsForm, self).__init__(*args, **kwargs)


class CustomFieldsMixin(object):
    urlname = None
    template_name = "custom_fields/custom_fields.html"
    # form_class = CustomFieldsForm
    page_name = ugettext_noop("Edit Custom Fields")
    doc_type = None

    def get_definition(self):
        return CustomFieldsDefinition.by_domain(self.domain, 'UserFields')

    def get_custom_fields(self):
        definition = self.get_definition()
        if definition:
            return definition.fields
        else:
            return [
                {"slug": "dob", "label": "not found", "is_required": True},
                {"slug": "gender", "label": "Gender", "is_required": False},
            ]

    def save_custom_fields(self, fields):
        definition = self.get_definition() or CustomFieldsDefinition()
        definition.doc_type = 'UserFields'
        definition.domain = self.domain
        definition.fields = [self.get_field(field) for field in json.loads(fields)]
        definition.save()

    def get_field(self, field):
        return CustomField(
            slug=field.get('slug'),
            is_required=field.get('is_required'),
            label=field.get('label'),
        )

    @property
    def page_context(self):
        return {
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
