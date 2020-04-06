from django import forms

from crispy_forms import layout as crispy
from crispy_forms.bootstrap import InlineField

from corehq.apps.hqwebapp.forms import BulkUploadForm


class LocationReassignmentRequestForm(BulkUploadForm):
    update = forms.BooleanField(label="Perform the updates", required=False,
                                initial=False)

    def crispy_form_fields(self, context):
        crispy_form_fields = super(LocationReassignmentRequestForm, self).crispy_form_fields(context)
        crispy_form_fields.extend([
            crispy.Div(InlineField('update'))
        ])
        return crispy_form_fields
