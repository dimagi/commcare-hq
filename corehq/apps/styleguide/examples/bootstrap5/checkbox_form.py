from django import forms
from django.utils.translation import gettext_lazy, gettext as _

from crispy_forms import (
    bootstrap as twbscrispy,
    layout as crispy,
)

from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.widgets import BootstrapCheckboxInput


class CheckboxDemoForm(forms.Form):
    height = forms.CharField(
        label=gettext_lazy("Height (cm)"),
    )
    smoking_status = forms.BooleanField(
        label=gettext_lazy("Smoking Status"),
        required=False,
        widget=BootstrapCheckboxInput(
            inline_label=gettext_lazy(
                "Patient has smoked on a habitual basis in the past 5 years"
            ),
        ),
        help_text=gettext_lazy(
            "*Habitual basis equates to at least five cigarettes a week."
        ),
    )
    heart_rate = forms.CharField(
        label=gettext_lazy("Heart Rate (bpm)"),
        required=False,
    )
    forward_results = forms.BooleanField(
        label=gettext_lazy("Forward results to GP"),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = hqcrispy.HQFormHelper()
        self.helper.form_method = 'POST'
        self.helper.form_action = '#'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Basic Information"),
                'height',  # Functions the same as crispy.Field below
                hqcrispy.CheckboxField('smoking_status'),
                crispy.Field('heart_rate'),
                'forward_results',
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Save"),
                    type="submit",
                    css_class="btn btn-primary",
                ),
                hqcrispy.LinkButton(
                    _("Cancel"),
                    '#',
                    css_class="btn btn-outline-primary",
                ),
            ),
        )
