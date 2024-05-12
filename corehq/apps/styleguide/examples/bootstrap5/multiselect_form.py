from django import forms
from django.utils.translation import gettext_lazy, gettext as _
from crispy_forms import bootstrap as twbscrispy, layout as crispy
from corehq.apps.hqwebapp import crispy as hqcrispy


class MultiselectDemoForm(forms.Form):
    team = forms.MultipleChoiceField(
        label=gettext_lazy("Team"),
        required=False,
        help_text=gettext_lazy("Make your team selection"),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # in theory, you can populate this from a parameter passed in args or kwargs
        self.fields['team'].choices = [
            (name, name) for name in [
                "Stephen Curry", "Nikola Jokic", "Joel Embiid", "Damian Lillard", "Kevin Durant", "Anthony Davis",
                "Jayson Tatum", "Paul George", "Zach LaVine", "Desmond Bane", "Bam Adebayo", "Karl-Anthony Towns"
            ]
        ]
        self.fields['team'].initial = [
            "Stephen Curry", "Jayson Tatum",
        ]

        self.helper = hqcrispy.HQFormHelper()
        self.helper.form_method = 'POST'
        self.helper.form_action = '#'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Team Builder"),
                'team',
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Save Team"),
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
