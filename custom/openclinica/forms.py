import logging
import bz2
from base64 import b64encode
from corehq.apps.hqwebapp import crispy as hqcrispy
from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from custom.openclinica.models import OpenClinicaSettings
from django import forms
from django.utils.translation import ugettext_lazy as _


class OpenClinicaSettingsForm(forms.Form):
    is_ws_enabled = forms.BooleanField(label=_('Enable web service'), required=False)
    url = forms.CharField(label=_('Web service URL'), required=False,
                          help_text=_('e.g. "http://openclinica.example.com:8080/"'))
    username = forms.CharField(label=_('Username'), required=False)
    password = forms.CharField(label=_('Password'), widget=forms.PasswordInput, required=False)
    protocol_id = forms.CharField(label=_('Study Protocol ID'), required=False, help_text=_('e.g. "BE 2014/03"'))
    metadata = forms.CharField(label=_('Study Metadata (CDISC ODM)'), widget=forms.Textarea, required=False,
                               help_text=_('Not required if web service is enabled'))

    def __init__(self, *args, **kwargs):
        super(OpenClinicaSettingsForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('Edit OpenClinica settings'),
                twbscrispy.PrependedText('is_ws_enabled', ''),

                crispy.Field('url'),
                crispy.Field('username'),
                crispy.Field('password'),
                crispy.Field('protocol_id'),

                crispy.Field('metadata'),
            ),
            hqcrispy.FormActions(
                StrictButton(
                    _("Update OpenClinica settings"),
                    type="submit",
                    css_class='btn-primary',
                )
            ),
        )

    def clean(self):

        def get_label(field):
            # Use `encode('utf8')` because label is a django.utils.functional.__proxy__ object
            return self.fields[field].label.encode('utf8')

        cleaned_data = super(OpenClinicaSettingsForm, self).clean()
        is_ws_enabled = cleaned_data.get('is_ws_enabled')
        if is_ws_enabled:
            missing = [f for f in ('url', 'username', 'protocol_id') if not cleaned_data.get(f)]
            if missing:
                raise forms.ValidationError(
                    '%(missing)s field(s) required if web service is enabled',
                    params={'missing': ', '.join(('"{}"'.format(get_label(m)) for m in missing))}
                )
        else:
            if not cleaned_data.get('metadata'):
                # Required if web service not enabled
                raise forms.ValidationError(
                    '%(missing)s field required if web service is not enabled',
                    params={'missing': '"{}"'.format(get_label('metadata'))}
                )

    def save(self, domain):
        try:
            settings = OpenClinicaSettings.for_domain(domain.name)
            if settings is None:
                settings = OpenClinicaSettings(domain=domain.name)
            settings.study.is_ws_enabled = self.cleaned_data['is_ws_enabled']
            settings.study.url = self.cleaned_data['url']
            settings.study.username = self.cleaned_data['username']
            if self.cleaned_data['password']:
                # Simple symmetric encryption. We don't need it to be strong, considering we'd have to store the
                # algorithm and the key together anyway; it just shouldn't be plaintext.
                settings.study.password = b64encode(bz2.compress(self.cleaned_data['password']))
            settings.study.protocol_id = self.cleaned_data['protocol_id']
            settings.study.metadata = self.cleaned_data['metadata']
            settings.save()
            return True
        except Exception as err:
            logging.error('Unable to save OpenClinica settings: %s' % err)
            return False
