from django import forms
from django.utils.translation import gettext_lazy as _

from crispy_forms import bootstrap as twbscrispy

from corehq.apps.hqwebapp.widgets import BootstrapCheckboxInput
from corehq.motech.repeaters.forms import GenericRepeaterForm

from .const import FHIR_VERSION_4_0_1, FHIR_VERSIONS


class FHIRRepeaterForm(GenericRepeaterForm):
    fhir_version = forms.ChoiceField(
        label=_('FHIR version'),
        choices=FHIR_VERSIONS,
        initial=FHIR_VERSION_4_0_1,
    )
    patient_registration_enabled = forms.BooleanField(
        label="",
        initial=True,
        required=False,
        help_text=_("Register new patients on the remote FHIR service?"),
        widget=BootstrapCheckboxInput(
            inline_label=_('Enable patient registration'),
        ),
    )
    patient_search_enabled = forms.BooleanField(
        label="",
        initial=False,
        required=False,
        help_text=_('Search the remote FHIR service for matching patients?'),
        widget=BootstrapCheckboxInput(
            inline_label=_("Enable patient search"),
        ),
    )

    def get_ordered_crispy_form_fields(self):
        fields = super().get_ordered_crispy_form_fields()
        return fields + [
            'fhir_version',
            twbscrispy.PrependedText('patient_registration_enabled', ''),
            twbscrispy.PrependedText('patient_search_enabled', ''),
        ]
