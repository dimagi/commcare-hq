from django import forms

from corehq.apps.users.forms import MultipleSelectionForm
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy
from corehq.apps.style import crispy as hqcrispy


class SLABEditLocationForm(MultipleSelectionForm):
    is_pilot = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super(SLABEditLocationForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False

        self.helper.layout = crispy.Layout(
            crispy.Field('is_pilot', data_bind='checked: isPilot'),
            crispy.Div(
                'selected_ids',
                data_bind='visible: isPilot()'
            ),
            hqcrispy.FormActions(
                crispy.ButtonHolder(
                    crispy.Submit('submit', 'Save')
                )
            )
        )
