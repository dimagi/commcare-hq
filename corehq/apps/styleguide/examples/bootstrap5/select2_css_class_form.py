from django import forms
from django.utils.translation import gettext_lazy, gettext as _
from crispy_forms import bootstrap as twbscrispy, layout as crispy
from corehq.apps.hqwebapp import crispy as hqcrispy


class Select2CssClassDemoForm(forms.Form):
    lake = forms.ChoiceField(
        label=gettext_lazy("Lake"),
        required=False,
        help_text=gettext_lazy("Select a lake you would like to visit"),
    )
    activities = forms.MultipleChoiceField(
        label=gettext_lazy("Activities"),
        choices=(
            ("kay", gettext_lazy("Kayak")),
            ("sup", gettext_lazy("SUP")),
            ("can", gettext_lazy("Canoe")),
            ("bot", gettext_lazy("Boat")),
            ("swi", gettext_lazy("Swim")),
        ),
        required=False,
        help_text=gettext_lazy("Select the activities you would like to do"),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # in theory, you can populate this from a parameter passed in args or kwargs
        self.fields['lake'].choices = [
            (lake, lake) for lake in [
                "Veluwemeer", "IJesselmeer", "Markermeer", "Gooimeer", "Westeinderplassen", "Kralingen",
                "Berkendonk", "Oldambtmeer", "Loosdrechste Plassen", "Zevenhuizplas", "Burgurmer Mar",
            ]
        ]

        self.helper = hqcrispy.HQFormHelper()
        self.helper.form_method = 'POST'
        self.helper.form_action = '#'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Activity Planner"),
                crispy.Field('lake', css_class="hqwebapp-select2"),
                crispy.Field('activities', css_class="hqwebapp-select2"),
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Create Schedule"),
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
