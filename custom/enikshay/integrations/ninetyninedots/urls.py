from __future__ import absolute_import

from __future__ import unicode_literals
from django.conf.urls import url

from custom.enikshay.integrations.ninetyninedots.views import (
    RegisterPatientRepeaterView,
    UpdateAdherenceRepeaterView,
    UpdatePatientRepeaterView,
    UpdateTreatmentOutcomeRepeaterView,
    UnenrollPatientRepeaterView,
)

urlpatterns = [
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
    url(
        r'^new_update_adherence_repeater$',
        UpdateAdherenceRepeaterView.as_view(),
        {'repeater_type': 'NinetyNineDotsAdherenceRepeater'},
        name=UpdateAdherenceRepeaterView.urlname
    ),
    url(
        r'^new_update_treatment_outcome_repeater$',
        UpdateAdherenceRepeaterView.as_view(),
        {'repeater_type': 'NinetyNineDotsTreatmentOutcomeRepeater'},
        name=UpdateTreatmentOutcomeRepeaterView.urlname
    ),
    url(
        r'^new_unenroll_patient_repeater$',
        UnenrollPatientRepeaterView.as_view(),
        {'repeater_type': 'NinetyNineDotsUnenrollPatientRepeater'},
        name=UnenrollPatientRepeaterView.urlname,
    ),
]
