from django.utils.translation import ugettext_lazy as _

from corehq.motech.repeaters.views import AddRepeaterView, EditRepeaterView

from .forms import FHIRRepeaterForm


class AddFHIRRepeaterView(AddRepeaterView):
    urlname = 'add_fhir_repeater'
    repeater_form_class = FHIRRepeaterForm
    page_title = _('Forward Cases to a FHIR API')
    page_name = _('Forward Cases to a FHIR API')

    def set_repeater_attr(self, repeater, cleaned_data):
        repeater = super().set_repeater_attr(repeater, cleaned_data)
        repeater.fhir_version = (self.add_repeater_form
                                 .cleaned_data['fhir_version'])
        return repeater


class EditFHIRRepeaterView(EditRepeaterView, AddFHIRRepeaterView):
    urlname = 'edit_fhir_repeater'
    page_title = _('Edit FHIR Repeater')
