import logging
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

    def clean(self):

        def get_label(field):
            # Use `encode('utf8')` because label is a django.utils.functional.__proxy__ object
            return self.fields[field].label.encode('utf8')

        cleaned_data = super(OpenClinicaSettingsForm, self).clean()
        is_ws_enabled = cleaned_data.get('is_ws_enabled')
        if is_ws_enabled:
            missing = [f for f in 'url', 'username', 'protocol_id' if not cleaned_data.get(f)]
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
                settings.study.password = self.cleaned_data['password']
            settings.study.protocol_id = self.cleaned_data['protocol_id']
            settings.study.metadata = self.cleaned_data['metadata']
            settings.save()
            return True
        except Exception as err:
            logging.error('Unable to save OpenClinica settings: %s' % err)
            return False
