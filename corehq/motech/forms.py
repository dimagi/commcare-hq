import re

from django import forms
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from email_validator import EmailNotValidError, validate_email

from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.motech.auth import api_auth_settings_choices
from corehq.motech.const import PASSWORD_PLACEHOLDER
from corehq.motech.models import ConnectionSettings


class ConnectionSettingsForm(forms.ModelForm):
    url = forms.CharField(
        label=_('URL'),
        help_text=_('e.g. "https://play.dhis2.org/dev/"')
    )
    api_auth_settings = forms.ChoiceField(
        label=_('API auth settings'),
        choices=api_auth_settings_choices,
        required=False,
    )
    username = forms.CharField(required=False)
    plaintext_password = forms.CharField(
        label=_('Password'),
        required=False,
        widget=forms.PasswordInput(render_value=True),
    )
    client_id = forms.CharField(
        label=_('Client ID'),
        required=False,
    )
    plaintext_client_secret = forms.CharField(
        label=_('Client secret'),
        required=False,
        widget=forms.PasswordInput,
    )
    skip_cert_verify = forms.BooleanField(
        label=_('Skip certificate verification'),
        help_text=_('Do not use in a production environment'),
        required=False,
    )
    notify_addresses_str = forms.CharField(
        label=_('Addresses to send notifications'),
        help_text=_('A comma-separated list of email addresses to send error '
                    'notifications'),
        required=False,
    )

    class Meta:
        model = ConnectionSettings
        fields = [
            'name',
            'url',
            'auth_type',
            'api_auth_settings',
            'username',
            'plaintext_password',
            'client_id',
            'plaintext_client_secret',
            'skip_cert_verify',
            'notify_addresses_str',
        ]

    def __init__(self, domain, *args, **kwargs):
        from corehq.motech.views import ConnectionSettingsListView

        if kwargs.get('instance'):
            # `plaintext_password` is not a database field, and so
            # super().__init__() will not update `initial` with it. We
            # need to do that here.
            #
            # We use PASSWORD_PLACEHOLDER to avoid telling the user what
            # the password is, but still indicating that it has been
            # set. (The password is only changed if its value is not
            # PASSWORD_PLACEHOLDER.)
            password = kwargs['instance'].plaintext_password
            secret = kwargs['instance'].plaintext_client_secret
            if 'initial' in kwargs:
                kwargs['initial'].update({
                    'plaintext_password': PASSWORD_PLACEHOLDER if password else '',
                    'plaintext_client_secret': PASSWORD_PLACEHOLDER if secret else '',
                })
            else:
                kwargs['initial'] = {
                    'plaintext_password': PASSWORD_PLACEHOLDER if password else '',
                    'plaintext_client_secret': PASSWORD_PLACEHOLDER if secret else '',
                }
        super().__init__(*args, **kwargs)

        self.domain = domain
        self.helper = hqcrispy.HQFormHelper()
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('Remote API Connection'),
                crispy.Field('name'),
                crispy.Field('url'),
                crispy.Field('auth_type'),
                crispy.Field('api_auth_settings'),
                crispy.Field('username'),
                crispy.Field('plaintext_password'),
                crispy.Field('client_id'),
                crispy.Field('plaintext_client_secret'),
                twbscrispy.PrependedText('skip_cert_verify', ''),
                crispy.Field('notify_addresses_str'),
                self.test_connection_button,
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Save"),
                    type="submit",
                    css_class="btn btn-primary",
                ),
                hqcrispy.LinkButton(
                    _("Cancel"),
                    reverse(
                        ConnectionSettingsListView.urlname,
                        kwargs={'domain': self.domain},
                    ),
                    css_class="btn btn-default",
                ),
            ),
        )

    @property
    def test_connection_button(self):
        return crispy.Div(
            crispy.Div(
                twbscrispy.StrictButton(
                    _('Test Connection'),
                    type='button',
                    css_id='test-connection-button',
                    css_class='btn btn-default disabled',
                ),
                crispy.Div(
                    css_id='test-connection-result',
                    css_class='text-success hide',
                ),
                css_class=hqcrispy.CSS_ACTION_CLASS,
            ),
            css_class='form-group'
        )

    def clean_notify_addresses_str(self):
        emails = self.cleaned_data['notify_addresses_str']
        are_valid = (validate_email(e) for e in re.split('[, ]+', emails) if e)
        try:
            all(are_valid)
        except EmailNotValidError:
            raise forms.ValidationError(_("Contains an invalid email address."))
        return emails

    def save(self, commit=True):
        self.instance.domain = self.domain
        self.instance.plaintext_password = self.cleaned_data['plaintext_password']
        return super().save(commit)
