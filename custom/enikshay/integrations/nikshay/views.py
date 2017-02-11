from corehq.apps.repeaters.views import AddCaseRepeaterView


class RegisterNikshayPatientRepeaterView(AddCaseRepeaterView):
    urlname = 'register_nikshay_patient'
    page_title = "Register Nikshay Patients"
    page_name = "Register Nikshay Patients"


class NikshayTreatmentOutcomesView(AddCaseRepeaterView):
    urlname = 'nikshay_treatment_outcome'
    page_title = "Update Nikshay Treatment Outcomes"
    page_name = "Update Nikshay Treatment Outcomes"
