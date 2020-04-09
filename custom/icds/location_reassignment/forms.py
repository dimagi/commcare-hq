from django import forms
from django.utils.translation import ugettext_lazy

from crispy_forms import layout as crispy
from crispy_forms.bootstrap import InlineField

from corehq.apps.hqwebapp.forms import BulkUploadForm


class LocationReassignmentRequestForm(BulkUploadForm):
    VALIDATE = "validate"
    EMAIL_HOUSEHOLDS = "email_households"
    UPDATE = "update"
    action_type = forms.ChoiceField(choices=((VALIDATE, ugettext_lazy("Validate")),
                                             (EMAIL_HOUSEHOLDS, ugettext_lazy("Email Households")),
                                             (UPDATE, "Perform Reassignment")),
                                    initial=VALIDATE)

    def crispy_form_fields(self, context):
        crispy_form_fields = super(LocationReassignmentRequestForm, self).crispy_form_fields(context)
        crispy_form_fields.extend([
            crispy.Div(InlineField('action_type'), css_class='col-sm-2'),
        ])
        return crispy_form_fields
