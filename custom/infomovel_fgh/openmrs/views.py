from corehq.motech.repeaters.views import AddCaseRepeaterView


class RegisterOpenmrsPatientRepeaterView(AddCaseRepeaterView):
    urlname = 'register_openmrs_patient'
    page_title = "Register OpenMRS Patients"
    page_name = "Register OpenMRS Patients"
