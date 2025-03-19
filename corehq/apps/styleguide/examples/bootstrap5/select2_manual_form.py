from django import forms
from django.utils.translation import gettext_lazy, gettext as _
from crispy_forms import bootstrap as twbscrispy, layout as crispy
from corehq.apps.hqwebapp import crispy as hqcrispy


class Select2ManualDemoForm(forms.Form):
    location = forms.ChoiceField(
        label=gettext_lazy("Location"),
        required=False,
        help_text=gettext_lazy("Select the location you would like to see recommendations for."),
    )
    experiences = forms.MultipleChoiceField(
        label=gettext_lazy("Experiences"),
        required=False,
        help_text=gettext_lazy("Select the experiences you would like to have"),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # in theory, you can populate this from a parameter passed in args or kwargs
        self.fields['location'].choices = [
            (city, city) for city in [
                "Berlin", "Amsterdam", "Frankfurt", "Paris", "Stockholm", "Reykjavik", "Geneva", "The Hague",
                "Rome", "Oslo", "London", "Hamburg", "Copenhagen", "Cape Town", "New York", "Atlanta",
            ]
        ]
        self.fields['experiences'].choices = [
            (experience, experience) for experience in [
                "Food", "Museum", "Music", "Street Art", "Street Food", "Underground", "Buildings", "Monuments",
            ]
        ]

        self.helper = hqcrispy.HQFormHelper()
        self.helper.form_method = 'POST'
        self.helper.form_action = '#'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("City Adventure Planner"),
                'location',
                'experiences',
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Plan"),
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
