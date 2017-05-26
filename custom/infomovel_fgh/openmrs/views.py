from corehq.motech.repeaters.views import AddCaseRepeaterView


class OpenmrsRepeaterView(AddCaseRepeaterView):
    urlname = 'new_openmrs_repeater$'
    page_title = "Forward to OpenMRS"
    page_name = "Forward to OpenMRS"
