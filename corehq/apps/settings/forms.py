from datetime import datetime

from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.postgres.forms import SimpleArrayField
from django.utils.html import format_html
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout
from two_factor.forms import (
    DeviceValidationForm,
    MethodForm,
    TOTPDeviceForm,
)
from two_factor.plugins.phonenumber.forms import (
    PhoneNumberForm,
    PhoneNumberMethodForm,
)
from two_factor.plugins.phonenumber.utils import get_available_phone_methods
from two_factor.utils import totp_digits

from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.crispy import HQFormHelper
from corehq.apps.settings.exceptions import DuplicateApiKeyName
from corehq.apps.settings.validators import validate_international_phonenumber
from corehq.apps.users.models import CouchUser, HQApiKey


class HQPasswordChangeForm(PasswordChangeForm):
    new_password1 = forms.CharField(label=_('New password'),
                                    widget=forms.PasswordInput(),
                                    help_text='<span data-bind="text: passwordHelp, css: color">')

    def __init__(self, user, *args, **kwargs):

        super(HQPasswordChangeForm, self).__init__(user, *args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('Specify New Password'),
                'old_password',
                crispy.Field(
                    'new_password1',
                    data_bind="value: password, valueUpdate: 'input'",
                ),
                'new_password2',
                hqcrispy.FormActions(
                    twbscrispy.StrictButton(
                        _('Change Password'),
                        css_class='btn-primary',
                        type='submit',
                        data_bind="enable: passwordSufficient(), click: submitCheck"
                    )
                ),
                css_class='check-password',
            )
        )

    def save(self, commit=True):
        user = super(HQPasswordChangeForm, self).save(commit)
        couch_user = CouchUser.from_django_user(user)
        couch_user.last_password_set = datetime.utcnow()
        if commit:
            couch_user.save()
        return user


class HQPhoneNumberMethodForm(PhoneNumberMethodForm):
    number = forms.CharField(required=False,
                             label=_('Phone Number'),
                             widget=forms.TextInput(
                                 attrs={'placeholder': _('Start with +, followed by Country Code.')}))
    number.run_validators = validate_international_phonenumber

    def __init__(self, **kwargs):
        super(HQPhoneNumberMethodForm, self).__init__(**kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                '',
                'number',
                crispy.Div(crispy.Field('method'), css_class='radio')
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _('Next'),
                    css_class='btn-primary',
                    type='submit',
                )
            )
        )


class HQDeviceValidationForm(DeviceValidationForm):
    token = forms.IntegerField(required=False, label=_("Token"), min_value=1, max_value=int('9' * totp_digits()))

    def __init__(self, device, **kwargs):
        super(HQDeviceValidationForm, self).__init__(device, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        # Next button is defined first so the enter key triggers it
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                '',
                'token'
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _('Next'),
                    css_class='btn-primary',
                    type='submit',
                ),
                twbscrispy.StrictButton(
                    _('Back'),
                    css_class='btn-default',
                    type='submit',
                    value='method',
                    name='wizard_goto_step',
                ),
            )
        )

    def clean_token(self):
        token = self.cleaned_data['token']
        if not token or not self.device.verify_token(token):
            raise forms.ValidationError(self.error_messages['invalid_token'])
        return token


class HQTwoFactorMethodForm(MethodForm):
    def __init__(self, *, allow_phone_2fa, **kwargs):
        super().__init__(**kwargs)
        if not allow_phone_2fa:
            # Block people from setting up the phone method as their default
            phone_methods = [method.code for method in get_available_phone_methods()]
            self.fields['method'].choices = [
                (method, display_name)
                for method, display_name in self.fields['method'].choices
                if method not in phone_methods
            ]

        self.helper = FormHelper()
        self.helper.form_class = 'form form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        # Next button is defined first so the enter key triggers it
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                '',
                crispy.Div(crispy.Field('method'), css_class='radio')
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _('Next'),
                    css_class='btn-primary',
                    type='submit',
                ),
                twbscrispy.StrictButton(
                    _("Back"),
                    css_class='btn-default',
                    type='submit',
                    value='welcome',
                    name="wizard_goto_step",
                ),
            )
        )


class HQTOTPDeviceForm(TOTPDeviceForm):
    token = forms.IntegerField(required=False, label=_("Token"), min_value=1, max_value=int('9' * totp_digits()))

    def __init__(self, key, user, **kwargs):
        super(HQTOTPDeviceForm, self).__init__(key, user, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        # Next button is defined first so the enter key triggers it
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                '',
                'token'
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _('Next'),
                    css_class='btn-primary',
                    type='submit',
                ),
                twbscrispy.StrictButton(
                    _('Back'),
                    css_class='btn-default',
                    type='submit',
                    value='method',
                    name='wizard_goto_step',
                ),
            )
        )

    def save(self):
        couch_user = CouchUser.from_django_user(self.user)
        if couch_user.two_factor_auth_disabled_until:
            couch_user.two_factor_auth_disabled_until = None
            couch_user.save()
        return super(HQTOTPDeviceForm, self).save()


class HQPhoneNumberForm(PhoneNumberForm):
    number = forms.CharField(required=False,
                             label=_('Phone Number'),
                             validators=[validate_international_phonenumber],
                             widget=forms.TextInput(
                                 attrs={'placeholder': _('Start with +, followed by Country Code.')}))
    number.run_validators = validate_international_phonenumber

    def __init__(self, **kwargs):
        super(HQPhoneNumberForm, self).__init__(**kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        # Next button is defined first so the enter key triggers it
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                '',
                'number'
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _('Next'),
                    css_class='btn-primary',
                    type='submit',
                ),
                twbscrispy.StrictButton(
                    _('Back'),
                    css_class='btn-default',
                    type='submit',
                    value='method',
                    name='wizard_goto_step',
                ),
            )
        )


class HQApiKeyForm(forms.Form):
    ALL_DOMAINS = ''
    name = forms.CharField()
    ip_allowlist = SimpleArrayField(
        forms.GenericIPAddressField(
            protocol='ipv4',
        ),
        label=gettext_lazy("Allowed IP Addresses (comma separated)"),
        required=False,
    )
    domain = forms.ChoiceField(
        required=False,
        help_text=gettext_lazy("Limit the key's access to a single project space")
    )
    expiration_date = forms.DateTimeField(
        required=False,
        help_text=gettext_lazy("Date and time the API key should expire on")
    )

    def __init__(self, *args, **kwargs):
        self.couch_user = kwargs.pop('couch_user')
        super().__init__(*args, **kwargs)

        user_domains = self.couch_user.get_domains()
        all_domains = (self.ALL_DOMAINS, _('All Projects'))
        self.fields['domain'].choices = [all_domains] + [(d, d) for d in user_domains]
        self.helper = HQFormHelper()
        self.helper.layout = Layout(
            crispy.Fieldset(
                gettext_lazy("Add New API Key"),
                crispy.Field('name'),
                crispy.Field('domain'),
                crispy.Field('ip_allowlist'),
                crispy.Field('expiration_date', css_class='date-picker'),
            ),
            hqcrispy.FormActions(
                StrictButton(
                    format_html('<i class="fa fa-plus"></i> {}', _("Generate New API Key")),
                    css_class='btn btn-primary',
                    type='submit'
                )
            )
        )

    def create_key(self, user):
        try:
            HQApiKey.all_objects.get(name=self.cleaned_data['name'], user=user)
            raise DuplicateApiKeyName
        except HQApiKey.DoesNotExist:
            new_key = HQApiKey.objects.create(
                name=self.cleaned_data['name'],
                ip_allowlist=self.cleaned_data['ip_allowlist'],
                user=user,
                domain=self.cleaned_data['domain'] or '',
                expiration_date=self.cleaned_data['expiration_date'],
            )
            return new_key


class HQEmptyForm(forms.Form):

    def __init__(self, **kwargs):
        super(forms.Form, self).__init__(**kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _('Next'),
                    css_class='btn-primary',
                    type='submit',
                )
            )
        )
