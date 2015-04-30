from django import forms
from django.utils.translation import ugettext_noop, ugettext as _

# Bootstrap 3 Crispy Forms
from bootstrap3_crispy import layout as cb3_layout
from bootstrap3_crispy import helper as cb3_helper
from bootstrap3_crispy import bootstrap as twbscrispy
from corehq.apps.style import crispy as hqcrispy


class ContactDimagiForm(forms.Form):
    first_name = forms.CharField(
        label=ugettext_noop("First Name"),
        required=False,
    )
    last_name = forms.CharField(
        label=ugettext_noop("Last Name"),
        required=False,
    )
    company = forms.CharField(
        label=ugettext_noop("Company / Organization"),
        required=False,
    )
    email = forms.CharField(
        label=ugettext_noop("Email Address"),
        required=False,
    )
    phone_number = forms.CharField(
        label=ugettext_noop("Phone Number"),
        required=False,
    )
    country = forms.CharField(
        label=ugettext_noop("Country"),
        required=False,
    )
    details = forms.CharField(
        label=ugettext_noop(
            "What is your interest in CommCare and "
            "any specific questions you have?"
        ),
        required=False,
        widget=forms.Textarea,
    )

    def __init__(self, *args, **kwargs):
        super(ContactDimagiForm, self).__init__(*args, **kwargs)
        self.helper = cb3_helper.FormHelper()
        self.helper.form_method = 'POST'
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-sm-4'
        self.helper.field_class = 'col-sm-8'
        self.helper.layout = cb3_layout.Layout(
            hqcrispy.Field(
                'first_name',
                ng_model="contact.first_name",
            ),
            hqcrispy.Field(
                'last_name',
                ng_model="contact.last_name",
            ),
            hqcrispy.Field(
                'company',
                ng_model="contact.company",
            ),
            hqcrispy.Field(
                'email',
                type="email",
                required="",
                ng_model="contact.email",
            ),
            hqcrispy.Field(
                'phone_number',
                ng_model="contact.phone_number",
            ),
            hqcrispy.Field(
                'country',
                ng_model="contact.country",
            ),
            hqcrispy.Field(
                'details',
                ng_model="contact.details",
            ),
            twbscrispy.Div(
                cb3_layout.HTML("need yo email"),
                ng_if="showEmailError",
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Contact Dimagi"),
                    type='submit',
                    css_class='btn-primary',
                    ng_click="send_email(contact)",
                )
            )
        )

    def send_email(self):
        print "sending email, todo"
