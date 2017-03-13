from corehq.apps.repeaters.views import AddCaseRepeaterView


class RegisterNikshayPatientRepeaterView(AddCaseRepeaterView):
    urlname = 'register_nikshay_patient'
    page_title = "Register Nikshay Patients"
    page_name = "Register Nikshay Patients"


class NikshayPatientFollowupRepeaterView(AddCaseRepeaterView):
    urlname = 'nikshay_patient_followup'
    page_title = "Nikshay Patients Follow Up"
    page_name = "Nikshay Patients Follow Up"
