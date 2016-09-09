from django.conf.urls import patterns, url
from custom.enikshay.integrations.ninetyninedots.views import (
    RegisterPatientRepeaterView,
    UpdatePatientRepeaterView
)

urlpatterns = patterns(
    'custom.enikshay.integrations.ninetyninedots.views',
    url(r'^update_patient_adherence$', 'update_patient_adherence'),
    url(r'^update_adherence_confidence$', 'update_adherence_confidence'),
    url(r'^update_default_confidence$', 'update_default_confidence'),
    url(r'^update_default_confidence$', 'update_default_confidence'),
    url(
        r'^new_register_patient_repeater$',
        RegisterPatientRepeaterView.as_view(),
        {'repeater_type': 'NinetyNineDotsRegisterPatientRepeater'},
        name=RegisterPatientRepeaterView.urlname
    ),
    url(
        r'^new_update_patient_repeater$',
        UpdatePatientRepeaterView.as_view(),
        {'repeater_type': 'NinetyNineDotsUpdatePatientRepeater'},
        name=UpdatePatientRepeaterView.urlname
    ),
)
