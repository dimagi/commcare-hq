from __future__ import absolute_import
from __future__ import unicode_literals
from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from two_factor.forms import (
    PhoneNumberMethodForm, DeviceValidationForm, MethodForm,
    TOTPDeviceForm, PhoneNumberForm
)
from two_factor.validators import validate_international_phonenumber

from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy
from crispy_forms import bootstrap as twbscrispy
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.users.models import CouchUser

from django.utils.translation import ugettext as _
from django.utils.safestring import mark_safe

from datetime import datetime

from custom.nic_compliance.forms import EncodedPasswordChangeFormMixin


class HQPasswordChangeForm(EncodedPasswordChangeFormMixin, PasswordChangeForm):

    new_password1 = forms.CharField(label=_("New password"),
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
                css_class="check-password",
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
    number = forms.CharField(label=_("Phone Number"),
                             validators=[validate_international_phonenumber],
                             widget=forms.TextInput(
                                 attrs={'placeholder': _('Start with +, followed by Country Code.')}))

    def __init__(self, **kwargs):
        validate_international_phonenumber.message = _("Make sure to enter a valid phone number "
                                                       "starting with a +, followed by your country code.")
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
                    _("Back"),
                    css_class='btn-default',
                    type='submit',
                    value='method',
                    name="wizard_goto_step",
                ),
            )
        )


class HQTwoFactorMethodForm(MethodForm):

    def __init__(self, **kwargs):
        super(HQTwoFactorMethodForm, self).__init__(**kwargs)
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
                    _("Back"),
                    css_class='btn-default',
                    type='submit',
                    value='method',
                    name="wizard_goto_step",
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
                    _("Back"),
                    css_class='btn-default',
                    type='submit',
                    value='method',
                    name="wizard_goto_step",
                ),
            )
        )


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
