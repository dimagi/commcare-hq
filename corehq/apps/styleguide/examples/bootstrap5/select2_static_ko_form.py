from django import forms
from django.utils.translation import gettext_lazy, gettext as _
from crispy_forms import bootstrap as twbscrispy, layout as crispy
from corehq.apps.hqwebapp import crispy as hqcrispy


class Select2StaticKoForm(forms.Form):
    pastries = forms.MultipleChoiceField(
        label=gettext_lazy("Pastries"),
        required=False,
        help_text=gettext_lazy("Select pastry names you would like ChatGPT to create an enticing menu for"),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['pastries'].choices = [
            (pastry, pastry) for pastry in [
                "Mille-feuille", "Croissant", "Eclair", "Choux", "Cinnamon roll", "Tart", "Profiteroles",
                "Bear claw", "Croquembouche", "Baklava", "Cannoli", "Strudel", "Canele",
            ]
        ]

        self.helper = hqcrispy.HQFormHelper()
        self.helper.form_method = 'POST'
        self.helper.form_action = '#'
        self.helper.form_id = "ko-menu-generator"
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Menu Generator"),
                crispy.Field('pastries', data_bind="staticSelect2: {}"),
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Create Menu"),
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
