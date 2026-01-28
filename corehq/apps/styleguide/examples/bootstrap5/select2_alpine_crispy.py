import json

from crispy_forms import layout as crispy
from django import forms

from corehq.apps.hqwebapp import crispy as hqcrispy


class Select2AlpineForm(forms.Form):
    my_fav_color = forms.ChoiceField(
        label='Colors',
        choices=(
            ('', 'Any'),
            ('purple', 'Purple'),
            ('blue', 'Blue'),
            ('green', 'Green'),
            ('red', 'Red'),
        ),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = hqcrispy.HQFormHelper()
        self.helper.form_method = 'POST'
        self.helper.form_action = '#'

        alpine_data_model = {
            'color': self.fields['my_fav_color'].initial,
        }

        # Layout: Alpine is used to toggle visibility of the "value" field
        # based on the selected match type.
        self.helper.layout = crispy.Layout(
            crispy.Div(
                crispy.Field(
                    'my_fav_color',
                    x_select2=json.dumps(
                        {
                            'placeholder': 'Select a Color',
                        }
                    ),
                    **(
                        {
                            '@select2change': 'color = $event.detail',
                        }
                    ),
                ),
                # Bind the Alpine data model defined above to this wrapper <div>.
                x_data=json.dumps(alpine_data_model),
            ),
        )
