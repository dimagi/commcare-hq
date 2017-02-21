from django.conf.urls import url

from custom.enikshay.integrations.nikshay.views import RegisterNikshayPatientRepeaterView

urlpatterns = [
    url(
        r'^new_register_patient_repeater$',
        RegisterNikshayPatientRepeaterView.as_view(),
        {'repeater_type': 'NikshayRegisterPatientRepeater'},
        name=RegisterNikshayPatientRepeaterView.urlname
    ),
]
