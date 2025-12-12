import json

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from django import forms
from django.utils.safestring import mark_safe

from corehq.apps.hqwebapp import crispy as hqcrispy


class DatepickerAlpineForm(forms.Form):
    datepicker = forms.CharField(
        label="Date",
        required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = hqcrispy.HQFormHelper()
        self.helper.form_method = 'POST'
        self.helper.form_action = '#'

        alpine_data_model = {
            'datepicker': self.fields['datepicker'].initial,
        }

        # Layout: Alpine is used to toggle visibility of the "value" field
        # based on the selected match type.
        self.helper.layout = crispy.Layout(
            crispy.Div(
                twbscrispy.AppendedText(
                    'datepicker',
                    mark_safe(  # nosec: no user input
                        '<i class="fcc fcc-fd-datetime"></i>'
                    ),
                    x_datepicker=json.dumps(
                        {
                            'datetime': True,
                            'useInputGroup': True,
                        }
                    ),
                ),
                # Bind the Alpine data model defined above to this wrapper <div>.
                x_data=json.dumps(alpine_data_model),
            ),
        )
