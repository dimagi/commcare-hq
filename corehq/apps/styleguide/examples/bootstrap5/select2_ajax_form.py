from django import forms
from django.urls import reverse
from django.utils.translation import gettext_lazy, gettext as _
from crispy_forms import bootstrap as twbscrispy, layout as crispy
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.widgets import Select2Ajax


class Select2AjaxDemoForm(forms.Form):
    user_filter = forms.Field(
        label=gettext_lazy("Users(s)"),
        required=False,
        widget=Select2Ajax(multiple=True),
        help_text=gettext_lazy("Select the users you want to view data for"),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user_filter'].widget.set_url(
            reverse("styleguide_data_select2_ajax_demo")
        )

        self.helper = hqcrispy.HQFormHelper()
        self.helper.form_method = 'POST'
        self.helper.form_action = '#'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Choose Filters"),
                'user_filter',
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Search"),
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
