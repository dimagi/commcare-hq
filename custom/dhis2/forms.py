from __future__ import print_function
import logging
from corehq.apps.style.crispy import B3MultiField, FormActions
from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset
from custom.dhis2.models import Dhis2Settings
from django import forms
from django.utils.translation import ugettext_lazy as _


logger = logging.getLogger(__name__)


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

    def __init__(self, *args, **kwargs):
        super(Dhis2SettingsForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'

        self.helper.layout = Layout(
            Fieldset(
                _('DHIS2 API Settings'),
                B3MultiField('Enable DHIS2', 'enabled'),
                'host',
                'username',
                'password',
                'top_org_unit_name',
                FormActions(
                    StrictButton(
                        _("Update DHIS2 API Settings"),
                        type="submit",
                        css_class="btn btn-primary",
                        css_id="update-dhis2-settings",
                        data_bind="hqbSubmitReady: form_is_ready",
                    ),
                ),
            )
        )

    def save(self, domain):
        try:
            settings = Dhis2Settings.for_domain(domain.name)
            if settings is None:
                # Create settings
                settings = Dhis2Settings()
                settings.domain = domain.name
                settings.dhis2 = {
                    'enabled': self.cleaned_data['enabled'],
                    'host': self.cleaned_data['host'],
                    'username': self.cleaned_data['username'],
                    'password': self.cleaned_data['password'],
                    'top_org_unit_name': self.cleaned_data['top_org_unit_name'],
                }
                settings.save()
            else:
                # Update settings
                settings.dhis2.update({
                    'enabled': self.cleaned_data['enabled'],
                    'host': self.cleaned_data['host'],
                    'username': self.cleaned_data['username'],
                    'top_org_unit_name': self.cleaned_data['top_org_unit_name'],
                })
                # Only update the password if it has been set
                if self.cleaned_data['password']:
                    settings.dhis2['password'] = self.cleaned_data['password']
                settings.save()
            return True
        except Exception as err:  # TODO: What Exception?
            logger.error('Unable to save DHIS2 API settings: %s' % err)
            return False
