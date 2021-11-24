import re

from django import forms
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from email_validator import EmailNotValidError, validate_email

from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.motech.const import AUTH_PRESETS, PASSWORD_PLACEHOLDER
from corehq.motech.models import ConnectionSettings
from corehq.motech.requests import validate_user_input_url_for_repeaters
from corehq.motech.utils import api_setting_matches_preset, get_endpoint_url
from corehq.util.urlvalidate.ip_resolver import CannotResolveHost
from corehq.util.urlvalidate.urlvalidate import PossibleSSRFAttempt


class ConnectionSettingsForm(forms.ModelForm):
    url = forms.CharField(
        label=_('URL'),
        help_text=_('e.g. "https://play.dhis2.org/dev/"')
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
        widget=forms.PasswordInput(render_value=True),
    )
    token_url = forms.CharField(
        label=_('Token URL'),
        required=False,
        help_text=_('e.g. "https://play.dhis2.org/dev/uaa/oauth/token"'),
    )
    refresh_url = forms.CharField(
        label=_('Token Refresh URL'),
        required=False,
        help_text=_('e.g. "https://play.dhis2.org/dev/uaa/oauth/token"'),
    )
    pass_credentials_in_header = forms.BooleanField(
        label=_('Pass credentials in header'),
        help_text=_('Pass credentials in Basic Auth header when requesting a token'),
        required=False,
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
        required=True,
    )
    auth_preset = forms.ChoiceField(
        label=_("API auth preset"),
        choices=[
            (preset_slug, preset.friendly_name) for preset_slug, preset in AUTH_PRESETS.items()
        ] + [('CUSTOM', _("(Custom)")), (None, _("(Not Applicable)"))],
        initial=None,
        required=False,
    )

    class Meta:
        model = ConnectionSettings
        fields = [
            'name',
            'url',
            'auth_type',
            'username',
            'plaintext_password',
            'client_id',
            'plaintext_client_secret',
            'skip_cert_verify',
            'notify_addresses_str',
            'token_url',
            'refresh_url',
            'pass_credentials_in_header',
        ]

    def __init__(self, domain, *args, **kwargs):
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
                    'auth_preset': api_setting_matches_preset(kwargs['instance']),
                })
            else:
                kwargs['initial'] = {
                    'plaintext_password': PASSWORD_PLACEHOLDER if password else '',
                    'plaintext_client_secret': PASSWORD_PLACEHOLDER if secret else '',
                    'auth_preset': api_setting_matches_preset(kwargs['instance']),
                }
        super().__init__(*args, **kwargs)

        self.domain = domain

    @cached_property
    def helper(self):
        from corehq.motech.views import ConnectionSettingsListView

        helper = hqcrispy.HQFormHelper()
        helper.layout = crispy.Layout(
            crispy.Field('name'),
            crispy.Field('notify_addresses_str'),
            crispy.Field('url'),
            crispy.Field('auth_type'),
            crispy.Field('username'),
            crispy.Field('plaintext_password'),
            crispy.Field('client_id'),
            crispy.Field('plaintext_client_secret'),
            crispy.Fieldset(
                _("Api Auth Settings"),
                crispy.Field('auth_preset'),
                crispy.Field('token_url'),
                crispy.Field('refresh_url'),
                twbscrispy.PrependedText('pass_credentials_in_header', ''),
            ),
            twbscrispy.PrependedText('skip_cert_verify', ''),
            self.test_connection_button,

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

        return helper

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

    def clean_url(self):
        return self._clean_url(self.cleaned_data['url'])

    def clean_token_url(self):
        return self._clean_url(self.cleaned_data['token_url'])

    def clean_refresh_url(self):
        return self._clean_url(self.cleaned_data['refresh_url'])

    def _clean_url(self, url):
        try:
            validate_user_input_url_for_repeaters(url, domain=self.domain, src='save_config')
        except CannotResolveHost:
            # Catching and wrapping this error means that unreachable hosts do not cause the form to be invalid.
            # The reason this is important is because we want to accept configurations where the host has not
            # been set up yet. Wrapping this value lets consumers check whether or not the host is recognized
            # before making a potentially unsafe request to it (i.e. '::1' looks unresolvable to IPv4,
            # but is actually the loopback address for IPv6)
            return UnrecognizedHost(url)
        except PossibleSSRFAttempt:
            raise forms.ValidationError(_("Invalid URL"))
        return url

    def save(self, commit=True):
        self.instance.domain = self.domain
        self.instance.plaintext_password = self.cleaned_data['plaintext_password']
        self.instance.plaintext_client_secret = self.cleaned_data['plaintext_client_secret']
        self.instance.last_token = None

        new_auth_preset = self.cleaned_data['auth_preset'] in AUTH_PRESETS
        url_changed_and_preset_set = (
            'url' in self.changed_data
            and api_setting_matches_preset(self.instance) in AUTH_PRESETS
        )
        if new_auth_preset or url_changed_and_preset_set:
            self._update_api_settings()

        preset_unset = not self.cleaned_data['auth_preset']
        if preset_unset:
            self.instance.token_url = None
            self.instance.refresh_url = None
            self.instance.pass_credentials_in_header = None

        return super().save(commit)

    def _update_api_settings(self):
        preset = AUTH_PRESETS[self.cleaned_data['auth_preset']]
        self.instance.token_url = get_endpoint_url(self.instance.url, preset.token_endpoint)
        self.instance.refresh_url = get_endpoint_url(self.instance.url, preset.refresh_endpoint)
        self.instance.pass_credentials_in_header = preset.pass_credentials_in_header


class UnrecognizedHost:
    def __init__(self, hostname):
        self.hostname = hostname

    def __repr__(self):
        return self.hostname
