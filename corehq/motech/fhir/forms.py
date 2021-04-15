from django import forms
from django.utils.translation import ugettext_lazy as _

from oauth2_provider.forms import AllowForm

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


class OAuthAllowForm(AllowForm):

    def __init__(self, cases, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['case_id'] = forms.ChoiceField(choices=cases)
