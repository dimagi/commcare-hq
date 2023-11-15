from django import forms
from django.utils.translation import gettext_lazy, gettext as _

from crispy_forms import (
    bootstrap as twbscrispy,
    layout as crispy,
)

from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.widgets import BootstrapSwitchInput


class SwitchDemoForm(forms.Form):
    email = forms.CharField(
        label=gettext_lazy("Email"),
    )
    enable_tracking = forms.BooleanField(
        label=gettext_lazy("Enable Tracking"),
        required=False,
        widget=BootstrapSwitchInput(
            inline_label=gettext_lazy(
                "Allow Dimagi to collect usage information to improve CommCare."
            ),
        ),
        help_text=gettext_lazy(
            "You can learn more about the information we collect and the ways we use it in our privacy policy"
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = hqcrispy.HQFormHelper()
        self.helper.form_method = 'POST'
        self.helper.form_action = '#'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Basic Information"),
                'email',
                twbscrispy.PrependedText('enable_tracking', ''),
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Update Settings"),
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
