from django import forms
from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy

from corehq.apps.hqwebapp import crispy as hqcrispy


class ExampleUserLoginForm(forms.Form):
    """
    This is an EXAMPLE form that demonstrates the use of Crispy Forms in HQ.
    """
    full_name = forms.CharField(
        label=gettext_noop("Full Name"),
    )
    email = forms.EmailField(
        label=gettext_noop("Email"),
    )
    password = forms.CharField(
        label=gettext_noop("Password"),
        widget=forms.PasswordInput(),
    )
    password_repeat = forms.CharField(
        label=gettext_noop("Password (Repeat)"),
        widget=forms.PasswordInput(),
    )
    phone_number = forms.CharField(
        label=gettext_noop("Phone Number"),
        required=False,
    )
    is_staff = forms.BooleanField(
        label=gettext_noop("Has Staff Privileges"),
        required=False,
    )
    language = forms.ChoiceField(
        label=gettext_noop("Language"),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super(ExampleUserLoginForm, self).__init__(*args, **kwargs)

        # Here's what makes the form a Crispy Form and adds in a few Bootstrap classes
        self.helper = hqcrispy.HQFormHelper()

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
                hqcrispy.CheckboxField('phone_number', placeholder='15555555555'),
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(_("Create User"),
                                        type='submit',
                                        css_class='btn-primary'),
                twbscrispy.StrictButton(_("Cancel"), css_class='btn-default'),
            ),
        )
