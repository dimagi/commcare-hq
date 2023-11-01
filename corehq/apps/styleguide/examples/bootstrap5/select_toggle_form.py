from django import forms
from django.utils.translation import gettext_lazy, gettext as _
from crispy_forms import bootstrap as twbscrispy, layout as crispy
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.widgets import SelectToggle

COLOR_CHOICES = [
    ('r', gettext_lazy('Red')),
    ('g', gettext_lazy('Green')),
    ('b', gettext_lazy('Blue'))
]


class SelectToggleDemoForm(forms.Form):
    color = forms.ChoiceField(
        label=gettext_lazy("Color"),
        required=False,
        choices=COLOR_CHOICES,  # we need to specify this twice for form validation
        widget=SelectToggle(
            choices=COLOR_CHOICES,
            apply_bindings=True,
            attrs={},  # you can specify ko_value or other select-toggle parameters here
        ),
        help_text=gettext_lazy("What is your favorite primary color"),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = hqcrispy.HQFormHelper()
        self.helper.form_method = 'POST'
        self.helper.form_action = '#'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Color Chooser"),
                'color',
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
