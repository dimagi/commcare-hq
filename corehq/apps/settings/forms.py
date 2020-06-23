from datetime import datetime

from django import forms
from django.conf import settings
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.postgres.forms import SimpleArrayField
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout
from two_factor.forms import (
    DeviceValidationForm,
    MethodForm,
    PhoneNumberForm,
    PhoneNumberMethodForm,
    TOTPDeviceForm,
)
from two_factor.models import get_available_phone_methods
from two_factor.utils import totp_digits

from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.crispy import HQFormHelper
from corehq.apps.settings.exceptions import DuplicateApiKeyName
from corehq.apps.settings.validators import validate_international_phonenumber
from corehq.apps.users.models import CouchUser, HQApiKey
from custom.nic_compliance.forms import EncodedPasswordChangeFormMixin


class HQPasswordChangeForm(EncodedPasswordChangeFormMixin, PasswordChangeForm):

    new_password1 = forms.CharField(label=_('New password'),
                                    widget=forms.PasswordInput(),
                                    help_text=mark_safe("""
                                    <span data-bind="text: passwordHelp, css: color">
                                    """))

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
                css_class='check-password',
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _('Change Password'),
                    css_class='btn-primary',
                    type='submit',
                )
            ),
        )

    def clean_old_password(self):
        from corehq.apps.hqwebapp.utils import decode_password
        self.cleaned_data['old_password'] = decode_password(self.cleaned_data['old_password'])
        return super(HQPasswordChangeForm, self).clean_old_password()

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

    def __init__(self, **kwargs):
        super(HQDeviceValidationForm, self).__init__(**kwargs)
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

    def __init__(self, **kwargs):
        super(HQTwoFactorMethodForm, self).__init__(**kwargs)
        if not settings.ALLOW_PHONE_AS_DEFAULT_TWO_FACTOR_DEVICE:
            # Block people from setting up the phone method as their default
            phone_methods = [method for method, _ in get_available_phone_methods()]
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
                    value='welcome_setup',
                    name="wizard_goto_step",
                ),
            )
        )


class HQTOTPDeviceForm(TOTPDeviceForm):
    token = forms.IntegerField(required=False, label=_("Token"), min_value=1, max_value=int('9' * totp_digits()))

    def __init__(self, **kwargs):
        super(HQTOTPDeviceForm, self).__init__(**kwargs)
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
    name = forms.CharField()
    ip_allowlist = SimpleArrayField(
        forms.GenericIPAddressField(),
        label=ugettext_lazy("Allowed IP Addresses (comma separated)"),
        required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = HQFormHelper()
        self.helper.layout = Layout(
            crispy.Fieldset(
                ugettext_lazy("Add New API Key"),
                crispy.Field('name'),
                crispy.Field('ip_allowlist'),
            ),
            hqcrispy.FormActions(
                StrictButton(
                    mark_safe('<i class="fa fa-plus"></i> {}'.format(ugettext_lazy("Generate New API Key"))),
                    css_class='btn btn-primary',
                    type='submit'
                )
            )
        )

    def create_key(self, user):
        try:
            HQApiKey.objects.get(name=self.cleaned_data['name'], user=user)
            raise DuplicateApiKeyName
        except HQApiKey.DoesNotExist:
            new_key = HQApiKey.objects.create(
                name=self.cleaned_data['name'],
                ip_allowlist=self.cleaned_data['ip_allowlist'],
                user=user,
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
