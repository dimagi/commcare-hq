from django import forms
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy

from corehq.apps.hqwebapp import crispy as hqcrispy


class ErrorsCrispyExampleForm(forms.Form):
    full_name = forms.CharField(
        label=gettext_lazy("Full Name"),
    )
    note = forms.CharField(
        label=gettext_lazy("Note"),
        required=False,
        help_text=gettext_lazy("This field will always error.")
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = hqcrispy.HQFormHelper()
        self.helper.form_action = "#form-errors"

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Error State Test"),
                'full_name',
                'note',
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Submit Form"),
                    type="submit",
                    css_class="btn btn-primary",
                ),
            ),
        )

    def clean_note(self):
        # we can validate the value of note and throw ValidationErrors here
        # FYI this part is standard Django Forms functionality and unrelated to Crispy Forms
        raise forms.ValidationError(_("This is a field-level error for the field 'note'."))
