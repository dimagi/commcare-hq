from django.conf.urls import url

from custom.enikshay.integrations.nikshay.views import (
    RegisterNikshayPatientRepeaterView,
    NikshayTreatmentOutcomesView,
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
]
