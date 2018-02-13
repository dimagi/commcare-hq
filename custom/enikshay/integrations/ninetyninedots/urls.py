from __future__ import absolute_import

from django.conf.urls import url

from custom.enikshay.integrations.ninetyninedots.views import (
    RegisterPatientRepeaterView,
    UpdateAdherenceRepeaterView,
    UpdatePatientRepeaterView,
    UpdateTreatmentOutcomeRepeaterView,
    UnenrollPatientRepeaterView,
    update_adherence_confidence,
    update_default_confidence,
    update_patient_adherence,
    update_patient_details,
)

urlpatterns = [
    url(r'^update_patient_adherence$', update_patient_adherence, name='update_patient_adherence'),
    url(r'^update_patient_details$', update_patient_details, name='update_patient_details'),
    url(r'^update_adherence_confidence$', update_adherence_confidence, name='update_adherence_confidence'),
    url(r'^update_default_confidence$', update_default_confidence, name='update_default_confidence'),
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
