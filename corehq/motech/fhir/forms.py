from django import forms
from django.utils.translation import ugettext_lazy as _

from corehq.motech.repeaters.forms import GenericRepeaterForm

from .const import FHIR_VERSION_4_0_1, FHIR_VERSIONS


class FHIRRepeaterForm(GenericRepeaterForm):
    fhir_version = forms.ChoiceField(
        label=_('FHIR version'),
        choices=FHIR_VERSIONS,
        initial=FHIR_VERSION_4_0_1,
    )

    def get_ordered_crispy_form_fields(self):
        fields = super().get_ordered_crispy_form_fields()
        return fields + ['fhir_version']
