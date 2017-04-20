from crispy_forms import layout
from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from django import forms
from django.utils.translation import ugettext as _
from corehq.apps.motech.connected_accounts import save_openmrs_account
from corehq.apps.style import crispy


class OpenmrsInstanceForm(forms.Form):
    server_url = forms.URLField()
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super(OpenmrsInstanceForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.all().wrap_together(layout.Fieldset, 'Edit Server Information')
        self.helper.layout.append(
            crispy.FormActions(
                StrictButton(
                    _("Update Server Info"),
                    type="submit",
                    css_class='btn-primary',
                )
            )
        )

    def save(self, domain):
        save_openmrs_account(
            domain, self.cleaned_data['server_url'], self.cleaned_data['username'],
            self.cleaned_data['password'])
