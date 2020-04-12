from django import forms
from django.utils.translation import ugettext

from crispy_forms import layout as crispy
from crispy_forms.bootstrap import InlineField

from corehq.apps.hqwebapp.forms import BulkUploadForm
from corehq.apps.hqwebapp.widgets import SelectToggle


class LocationReassignmentRequestForm(BulkUploadForm):
    VALIDATE = "validate"
    EMAIL_HOUSEHOLDS = "email_households"
    UPDATE = "update"
    ACTION_TYPE_CHOICES = [(VALIDATE, ugettext("Validate")),
                           (EMAIL_HOUSEHOLDS, ugettext("Email Households")),
                           (UPDATE, ugettext("Perform Reassignment"))]
    action_type = forms.ChoiceField(choices=ACTION_TYPE_CHOICES,
                                    initial=VALIDATE,
                                    widget=SelectToggle(choices=ACTION_TYPE_CHOICES))

    def crispy_form_fields(self, context):
        crispy_form_fields = super(LocationReassignmentRequestForm, self).crispy_form_fields(context)
        crispy_form_fields.extend([
            crispy.Div(InlineField('action_type')),
        ])
        return crispy_form_fields
