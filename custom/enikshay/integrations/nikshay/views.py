from __future__ import absolute_import
from corehq.motech.repeaters.views import (
    AddCaseRepeaterView,
    AddCustomSOAPCaseRepeaterView,
    AddCustomSOAPLocationRepeaterView,
)


class RegisterNikshayPatientRepeaterView(AddCaseRepeaterView):
    urlname = 'register_nikshay_patient'
    page_title = "Register Nikshay Patients"
    page_name = "Register Nikshay Patients"


class NikshayTreatmentOutcomesView(AddCaseRepeaterView):
    urlname = 'nikshay_treatment_outcome'
    page_title = "Update Nikshay Treatment Outcomes"
    page_name = "Update Nikshay Treatment Outcomes"


class NikshayHIVTestRepeaterView(AddCaseRepeaterView):
    urlname = 'nikshay_patient_hiv_test'
    page_title = "Nikshay Patients HIV Test"
    page_name = "Nikshay Patients HIV Test"


class NikshayPatientFollowupRepeaterView(AddCaseRepeaterView):
    urlname = 'nikshay_patient_followup'
    page_title = "Nikshay Patients Follow Up"
    page_name = "Nikshay Patients Follow Up"


class RegisterNikshayPrivatePatientRepeaterView(AddCustomSOAPCaseRepeaterView):
    urlname = 'register_nikshay_private_patient'
    page_title = "Register Nikshay Private Patients"
    page_name = "Register Nikshay Private Patients"


class RegisterNikshayHealthEstablishmentRepeaterView(AddCustomSOAPLocationRepeaterView):
    urlname = 'register_nikshay_health_establishment'
    page_title = "Register Nikshay Health Establishment"
    page_name = "Register Nikshay Health Establishment"
