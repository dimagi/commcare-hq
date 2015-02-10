from custom.dhis2.models import Dhis2Settings
from django import forms
from django.utils.translation import ugettext as _


class Dhis2SettingsForm(forms.Form):
    """
    Form for updating DHIS2 API settings
    """
    enabled = forms.BooleanField(initial=False, required=False)
    host = forms.CharField(
        label=_('DHIS2 API host'),
        help_text=_('e.g. "http://dhis2.changeme.com:8123/dhis"'),
        required=False)
    username = forms.CharField(label=_('Username'), required=False)
    password = forms.CharField(
        label=_('Password'),
        widget=forms.PasswordInput,
        required=False)
    top_org_unit_name = forms.CharField(
        label=_('Top org unit name'),
        help_text=_('The name of the DHIS2 organisation unit below which this project is relevant. '
                    'e.g. "Fermathe Clinic"'),
        required=False)

    def save(self, domain):
        settings = Dhis2Settings.for_domain(domain.name)
        fields = ('enabled', 'host', 'username', 'password', 'top_org_unit_name')
        if settings is None:
            dhis2_data = {f: self.cleaned_data[f] for f in fields}
            settings = Dhis2Settings()
            settings.domain = domain.name
            for field in fields:
                setattr(settings.dhis2, field, self.cleaned_data[field])
            settings.save()
        else:
            for field in fields:
                setattr(settings.dhis2, field, self.cleaned_data[field])
            settings.save()
        return True
