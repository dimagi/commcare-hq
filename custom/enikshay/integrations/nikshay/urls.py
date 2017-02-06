from django.conf.urls import url

from custom.enikshay.integrations.nikshay.views import (
    RegisterNikshayPatientRepeaterView,
    NikshayPatientFollowupRepeaterView,
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
        r'^new_register_patient_repeater$',
        NikshayPatientFollowupRepeaterView.as_view(),
        {'repeater_type': 'NikshayFollowupRepeater'},
        name=NikshayPatientFollowupRepeaterView.urlname
    ),
    url(
        r'^new_register_patient_repeater$',
        NikshayHIVTestRepeaterView.as_view(),
        {'repeater_type': 'NikshayHIVTestRepeater'},
        name=NikshayHIVTestRepeaterView.urlname
    ),
]
