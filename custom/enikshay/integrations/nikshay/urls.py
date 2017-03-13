from django.conf.urls import url

from custom.enikshay.integrations.nikshay.views import (
    RegisterNikshayPatientRepeaterView,
    NikshayHIVTestRepeaterView,
)

urlpatterns = [
    url(
        r'^new_register_patient_repeater$',
        RegisterNikshayPatientRepeaterView.as_view(),
        {'repeater_type': 'NikshayRegisterPatientRepeater'},
        name=RegisterNikshayPatientRepeaterView.urlname
    ),
    url(
        r'^patient_hiv_test_repeater$',
        NikshayHIVTestRepeaterView.as_view(),
        {'repeater_type': 'NikshayHIVTestRepeater'},
        name=NikshayHIVTestRepeaterView.urlname
    ),
]
