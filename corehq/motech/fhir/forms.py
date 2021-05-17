from django import forms
from django.utils.translation import ugettext_lazy as _

from crispy_forms import bootstrap as twbscrispy
from oauth2_provider.forms import AllowForm

from corehq.motech.repeaters.forms import GenericRepeaterForm

from .const import FHIR_VERSION_4_0_1, FHIR_VERSIONS


class FHIRRepeaterForm(GenericRepeaterForm):
    fhir_version = forms.ChoiceField(
        label=_('FHIR version'),
        choices=FHIR_VERSIONS,
        initial=FHIR_VERSION_4_0_1,
    )
    patient_registration_enabled = forms.BooleanField(
        label=_('Enable patient registration'),
        initial=True,
        required=False,
        help_text=_('Register new patients on the remote FHIR service?'),
    )
    patient_search_enabled = forms.BooleanField(
        label=_('Enable patient search'),
        initial=False,
        required=False,
        help_text=_('Search the remote FHIR service for matching patients?'),
    )

    def get_ordered_crispy_form_fields(self):
        fields = super().get_ordered_crispy_form_fields()
        return fields + [
            'fhir_version',
            twbscrispy.PrependedText('patient_registration_enabled', ''),
            twbscrispy.PrependedText('patient_search_enabled', ''),
        ]


class OAuthAllowForm(AllowForm):

    def __init__(self, cases, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['case_id'] = forms.ChoiceField(choices=cases)
