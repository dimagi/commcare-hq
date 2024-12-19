from django import forms
from django.utils.translation import gettext_lazy, gettext as _
from crispy_forms import bootstrap as twbscrispy, layout as crispy
from corehq.apps.hqwebapp import crispy as hqcrispy


class Select2DynamicKoForm(forms.Form):
    genre = forms.ChoiceField(
        label=gettext_lazy("Genre"),
        required=False,
        help_text=gettext_lazy("Select the electronic music genre you want to generate a playlist"),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = hqcrispy.HQFormHelper()
        self.helper.form_method = 'POST'
        self.helper.form_action = '#'
        self.helper.form_id = "ko-playlist-generator"
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Playlist Creator"),
                crispy.Field('genre', data_bind="select2: genres, value: value"),
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Create Playlist"),
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
