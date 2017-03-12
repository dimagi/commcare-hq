from corehq.apps.repeaters.views import AddCaseRepeaterView


class RegisterNikshayPatientRepeaterView(AddCaseRepeaterView):
    urlname = 'register_nikshay_patient'
    page_title = "Register Nikshay Patients"
    page_name = "Register Nikshay Patients"


class NikshayHIVTestRepeaterView(AddCaseRepeaterView):
     urlname = 'nikshay_patient_hiv_test'
     page_title = "Nikshay Patients HIV Test"
     page_name = "Nikshay Patients HIV Test"
