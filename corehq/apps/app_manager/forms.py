from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import ButtonHolder, Fieldset, Hidden, Layout, Submit
from django import forms
from django.utils.translation import ugettext as _
from corehq.apps.domain.models import Domain


class CopyApplicationForm(forms.Form):
    domain = forms.CharField(
        label=_("Copy this app to project"),
        widget=forms.TextInput(attrs={"data-bind": "typeahead: domain_names"}))
    name = forms.CharField(required=False, label=_('Name'))

    def __init__(self, app_id, *args, **kwargs):
        super(CopyApplicationForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
            '<h3>%s</h3>' % _('Copy Application'),
                'domain',
                'name',
            ),
            Hidden('app', app_id),
            FormActions(
                ButtonHolder(
                    Submit('submit', '%s...' % _('Copy'))
                )
            )
        )

    def clean_domain(self):
        domain_name = self.cleaned_data['domain']
        domain = Domain.get_by_name(domain_name)
        if domain is None:
            raise forms.ValidationError("A valid project space is required.")
        return domain_name
