from django import forms
from django.utils.translation import ugettext_noop, ugettext as _
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy
from crispy_forms import bootstrap as twbscrispy
from corehq.apps.style import crispy as hqcrispy


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
    language = forms.ChoiceField(
        label=ugettext_noop("Language"),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super(ExampleUserLoginForm, self).__init__(*args, **kwargs)

        # Here's what makes the form a Crispy Form:
        self.helper = FormHelper()

        # This is necessary to make the form a horizontal form
        self.helper.form_class = 'form-horizontal'

        # What do all these col-sm-3, col-md-2, col-lg-6 things mean? They
        # specify the column sizes for the label and field columns depending
        # on what the screen size is. This is called Responsive Design, and
        # you should visit
        # [Bootstrap 3's Responsive Docs](http://getbootstrap.com/css/#responsive-utilities)
        # for more information.
        self.helper.label_class = 'col-sm-3 col-md-2 col-lg-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'

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
                twbscrispy.PrependedText('phone_number', '+',
                                         placeholder='15555555555'),
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(_("Create User"),
                                        type='submit',
                                        css_class='btn-primary'),
                twbscrispy.StrictButton(_("Cancel"), css_class='btn-default'),
            ),
        )
