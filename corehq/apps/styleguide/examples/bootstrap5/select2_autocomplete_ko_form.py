from django import forms
from django.utils.translation import gettext_lazy, gettext as _
from crispy_forms import bootstrap as twbscrispy, layout as crispy
from corehq.apps.hqwebapp import crispy as hqcrispy


class Select2AutocompleteKoForm(forms.Form):
    vegetable = forms.ChoiceField(
        label=gettext_lazy("Vegetable"),
        required=False,
        help_text=gettext_lazy("Select your favorite vegetable you want recipe suggestions for"),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = hqcrispy.HQFormHelper()
        self.helper.form_method = 'POST'
        self.helper.form_action = '#'
        self.helper.form_id = "ko-veggie-suggestions"
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Veggie Recipes"),
                crispy.Field('vegetable', data_bind="autocompleteSelect2: veggies, value: value"),
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Suggest Recipes"),
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
