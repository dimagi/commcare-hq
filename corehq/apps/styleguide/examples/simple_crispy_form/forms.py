from django import forms
from django.utils.translation import ugettext_noop, ugettext as _
from bootstrap3_crispy import bootstrap as twbs
from bootstrap3_crispy.helper import FormHelper
from bootstrap3_crispy import layout as crispy
from corehq.apps.style.crispy import FormActions


class ExampleUserLoginForm(forms.Form):
    """
    This is an EXAMPLE form that demonstrates the use of Crispy Forms in HQ.
    """
    full_name = forms.CharField(
        label=ugettext_noop("Full Name"),
    )
    email = forms.EmailField(
        label=ugettext_noop("Email"),
    )
    password = forms.CharField(
        label=ugettext_noop("Password"),
        widget=forms.PasswordInput(),
    )
    password_repeat = forms.CharField(
        label=ugettext_noop("Password (Repeat)"),
        widget=forms.PasswordInput(),
    )
    phone_number = forms.CharField(
        label=ugettext_noop("Phone Number"),
        required=False,
    )
    is_staff = forms.BooleanField(
        label=ugettext_noop("Has Staff Privileges"),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super(ExampleUserLoginForm, self).__init__(*args, **kwargs)

        # Here's what makes the form a Crispy Form:
        self.helper = FormHelper()

        # This is necessary to make the form a horizontal form
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-3'
        self.helper.field_class = 'col-lg-6'

        # This is the layout of the form where we can explicitly specify the
        # order of fields and group fields into fieldsets.
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                # This is the title for the group of fields that follows:
                _("Basic Information"),
                'full_name', # crispy.Field is used as the default display component
                crispy.Field('email'),  # effectively the same as the line above
                'password',
                'password_repeat',
            ),
            crispy.Fieldset(
                _("Advanced Information"),
                'is_staff',
                twbs.PrependedText('phone_number', '+',
                                   placeholder='15555555555'),
            ),
            FormActions(
                twbs.StrictButton(_("Create User"),
                                  type='submit',
                                  css_class='btn-primary'),
                twbs.StrictButton(_("Cancel"), css_class='btn-default'),
            ),
        )
