from django.forms import Form
from django.contrib.auth.forms import PasswordChangeForm
from two_factor.forms import (
    PhoneNumberMethodForm, DeviceValidationForm, MethodForm,
    TOTPDeviceForm, PhoneNumberForm
)

from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy
from crispy_forms import bootstrap as twbscrispy
from corehq.apps.style import crispy as hqcrispy

from django.utils.translation import ugettext as _


class HQPasswordChangeForm(PasswordChangeForm):

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
                'new_password1',
                'new_password2'
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _('Change Password'),
                    css_class='btn-primary',
                    type='submit',
                )
            )
        )


class HQPhoneNumberMethodForm(PhoneNumberMethodForm):

    def __init__(self, **kwargs):
        super(HQPhoneNumberMethodForm, self).__init__(**kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-3 col-md-4 col-lg-2'
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
        self.helper.field_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                '',
                'token'
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Back"),
                    css_class='btn-default',
                    type='submit',
                    value='setup',
                    name="wizard_goto_step",
                ),
                twbscrispy.StrictButton(
                    _('Next'),
                    css_class='btn-primary',
                    type='submit',
                ),
            )
        )


class HQTwoFactorMethodForm(MethodForm):

    def __init__(self, **kwargs):
        super(HQTwoFactorMethodForm, self).__init__(**kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                '',
                crispy.Div(crispy.Field('method'), css_class='radio')
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Back"),
                    css_class='btn-default',
                    type='submit',
                    value='welcome',
                    name="wizard_goto_step",
                ),
                twbscrispy.StrictButton(
                    _('Next'),
                    css_class='btn-primary',
                    type='submit',
                )
            )
        )


class HQTOTPDeviceForm(TOTPDeviceForm):

    def __init__(self, **kwargs):
        super(HQTOTPDeviceForm, self).__init__(**kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                '',
                'token'
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Back"),
                    css_class='btn-default',
                    type='submit',
                    value='method',
                    name="wizard_goto_step",
                ),
                twbscrispy.StrictButton(
                    _('Next'),
                    css_class='btn-primary',
                    type='submit',
                )
            )
        )


class HQPhoneNumberForm(PhoneNumberForm):

    def __init__(self, **kwargs):
        super(HQPhoneNumberForm, self).__init__(**kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                '',
                'number'
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Back"),
                    css_class='btn-default',
                    type='submit',
                    value='method',
                    name="wizard_goto_step",
                ),
                twbscrispy.StrictButton(
                    _('Next'),
                    css_class='btn-primary',
                    type='submit',
                )
            )
        )

class HQEmptyForm(Form):

    def __init__(self, **kwargs):
        super(Form, self).__init__(**kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.layout = crispy.Layout(
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _('Next'),
                    css_class='btn-primary',
                    type='submit',
                )
            )
        )