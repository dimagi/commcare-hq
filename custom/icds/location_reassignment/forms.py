from django import forms
from django.utils.translation import ugettext

from crispy_forms import layout as crispy
from crispy_forms.bootstrap import InlineField

from corehq.apps.hqwebapp.forms import BulkUploadForm
from corehq.apps.hqwebapp.widgets import SelectToggle
from custom.icds.location_reassignment.const import (
    EXTRACT_OPERATION,
    SPLIT_OPERATION,
)


class LocationReassignmentRequestForm(BulkUploadForm):
    VALIDATE = "validate"
    EMAIL_HOUSEHOLDS = "email_households"
    EMAIL_OTHER_CASES = "email_other_cases"
    UPDATE = "update"
    REASSIGN_HOUSEHOLDS = "reassign_households"
    REASSIGN_OTHER_CASES = "reassign_other_cases"
    ACTION_TYPE_CHOICES = [(VALIDATE, ugettext("Validate")),
                           (EMAIL_HOUSEHOLDS, ugettext("Email Households "
                                                       f"(Only for {SPLIT_OPERATION} and {EXTRACT_OPERATION})")),
                           (EMAIL_OTHER_CASES, ugettext("Email Other Cases "
                                                        f"(Only for {SPLIT_OPERATION} and {EXTRACT_OPERATION})")),
                           (UPDATE, ugettext("Perform Reassignment")),
                           (REASSIGN_HOUSEHOLDS, ugettext(
                               "Reassign Households "
                               f"(Only for {SPLIT_OPERATION} and {EXTRACT_OPERATION})")),
                           (REASSIGN_OTHER_CASES, ugettext(
                               "Reassign Other Cases "
                               f"(Only for {SPLIT_OPERATION} and {EXTRACT_OPERATION})")),
                           ]
    action_type = forms.ChoiceField(choices=ACTION_TYPE_CHOICES,
                                    initial=VALIDATE,
                                    )

    def crispy_form_fields(self, context):
        crispy_form_fields = super(LocationReassignmentRequestForm, self).crispy_form_fields(context)
        crispy_form_fields.extend([
            crispy.Div(InlineField('action_type'), css_class="col-sm-4"),
        ])
        return crispy_form_fields
