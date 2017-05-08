from django.conf.urls import url

from custom.infomovel_fgh.openmrs.views import (
    RegisterOpenmrsPatientRepeaterView,
)

urlpatterns = [
    url(
        r'^new_register_patient_repeater$',
        RegisterOpenmrsPatientRepeaterView.as_view(),
        {'repeater_type': 'RegisterOpenmrsPatientRepeater'},
        name=RegisterOpenmrsPatientRepeaterView.urlname
    ),
]
