from django import forms
from django.utils.translation import gettext

from crispy_forms import layout as crispy
# todo proper B3 Handle
from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper

from corehq.apps.hqwebapp import crispy as hqcrispy


class PrimeRestoreCacheForm(forms.Form):
    info_text = gettext(
        "For projects where mobile users manage a lot of cases (e.g. more than 10,000), "
        "this tool can be used to temporarily speed up phone sync times. Once activated, "
        "it will ensure that the 'Sync with Server' functionality runs faster on the phone for 24 hours.")

    def __init__(self, *args, **kwargs):
        super(PrimeRestoreCacheForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()

        self.helper.form_method = 'post'
        self.helper.form_action = '.'

        self.helper.layout = crispy.Layout(
            crispy.HTML("<p>" + self.info_text + "</p>"),
            hqcrispy.FormActions(
                StrictButton(
                    "Click here to speed up 'Sync with Server'",
                    css_class="btn-primary",
                    type="submit",
                ),
            ),
        )
