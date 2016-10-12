from crispy_forms.helper import FormHelper
from crispy_forms.layout import Fieldset, Hidden, Layout
from crispy_forms.bootstrap import StrictButton
from django import forms
from django.utils.translation import ugettext as _
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.domain.models import Domain
from corehq.apps.style import crispy as hqcrispy


class CopyApplicationForm(forms.Form):
    domain = forms.CharField(
        label=_("Copy this app to project"),
        widget=forms.TextInput(attrs={"data-bind": "typeahead: domain_names"}))
    name = forms.CharField(required=True, label=_('Name'))

    def __init__(self, from_domain, app_id, *args, **kwargs):
        export_zipped_apps_enabled = kwargs.pop('export_zipped_apps_enabled', False)
        super(CopyApplicationForm, self).__init__(*args, **kwargs)
        fields = ['domain', 'name']
        if app_id:
            app = get_app(from_domain, app_id)
            if app:
                self.fields['name'].initial = app.name
        if export_zipped_apps_enabled:
            self.fields['gzip'] = forms.FileField(required=False)
            fields.append('gzip')

        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = Layout(
            Fieldset(
                _('Copy Application'),
                *fields
            ),
            Hidden('app', app_id),
            StrictButton(_('Copy'), type='submit', css_class='btn-primary col-sm-offset-3 col-md-offset-4 col-lg-offset-2')
        )

    def clean_domain(self):
        domain_name = self.cleaned_data['domain']
        domain = Domain.get_by_name(domain_name)
        if domain is None:
            raise forms.ValidationError("A valid project space is required.")
        return domain_name
