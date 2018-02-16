from __future__ import absolute_import
from django.conf.urls import url

from custom.enikshay.integrations.nikshay.views import (
    RegisterNikshayPatientRepeaterView,
    NikshayTreatmentOutcomesView,
    NikshayHIVTestRepeaterView,
    NikshayPatientFollowupRepeaterView,
    RegisterNikshayPrivatePatientRepeaterView,
    RegisterNikshayHealthEstablishmentRepeaterView,
)

urlpatterns = [
    url(
        r'^new_register_patient_repeater$',
        RegisterNikshayPatientRepeaterView.as_view(),
        {'repeater_type': 'NikshayRegisterPatientRepeater'},
        name=RegisterNikshayPatientRepeaterView.urlname
    ),
    url(
        r'^treatment_outcomes_repeater$',
        NikshayTreatmentOutcomesView.as_view(),
        {'repeater_type': 'NikshayTreatmentOutcomeRepeater'},
        name=NikshayTreatmentOutcomesView.urlname
    ),
    url(
        r'^patient_hiv_test_repeater$',
        NikshayHIVTestRepeaterView.as_view(),
        {'repeater_type': 'NikshayHIVTestRepeater'},
        name=NikshayHIVTestRepeaterView.urlname
    ),
    url(
        r'^patient_followup_repeater$',
        NikshayPatientFollowupRepeaterView.as_view(),
        {'repeater_type': 'NikshayFollowupRepeater'},
        name=NikshayPatientFollowupRepeaterView.urlname
    ),
    url(
        r'^new_register_private_patient_repeater$',
        RegisterNikshayPrivatePatientRepeaterView.as_view(),
        {'repeater_type': 'NikshayRegisterPrivatePatientRepeater'},
        name=RegisterNikshayPrivatePatientRepeaterView.urlname
    ),
    url(
        r'^register_health_establishment_repeater$',
        RegisterNikshayHealthEstablishmentRepeaterView.as_view(),
        {'repeater_type': 'NikshayHealthEstablishmentRepeater'},
        name=RegisterNikshayHealthEstablishmentRepeaterView.urlname
    ),
]
