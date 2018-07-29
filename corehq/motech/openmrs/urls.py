from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url

from corehq.motech.openmrs.views import (
    openmrs_patient_identifier_types,
    openmrs_person_attribute_types,
    openmrs_raw_api,
    openmrs_test_fire,
    openmrs_edit_config,
    OpenmrsImporterView,
    openmrs_import_now,
)
from corehq.motech.repeaters.views.repeaters import AddOpenmrsRepeaterView


urlpatterns = [
    url(
        r'^new_openmrs_repeater$',
        AddOpenmrsRepeaterView.as_view(),
        {'repeater_type': 'OpenmrsRepeater'},
        name=AddOpenmrsRepeaterView.urlname
    ),
    url(
        r'^(?P<repeater_id>\w+)/edit_config/$',
        openmrs_edit_config,
        name='openmrs_edit_config',
    ),
    url(
        r'^(?P<repeater_id>\w+)/patientidentifiertypes/$',
        openmrs_patient_identifier_types,
        name='openmrs_patient_identifier_types',
    ),
    url(
        r'^(?P<repeater_id>\w+)/personattributetypes/$',
        openmrs_person_attribute_types,
        name='openmrs_person_attribute_types',
    ),
    url(
        r'^(?P<repeater_id>\w+)/api(?P<rest_uri>/.*)$',
        openmrs_raw_api,
        name='openmrs_raw_api',
    ),
    url(
        r'^(?P<repeater_id>\w+)/test_fire/(?P<record_id>\w+)/$',
        openmrs_test_fire,
        name='openmrs_test_fire',
    ),
    url(
        r'^importers/$',
        OpenmrsImporterView.as_view(),
        name=OpenmrsImporterView.urlname
    ),
    url(
        r'^importers/now/$',
        openmrs_import_now,
        name='openmrs_import_now',
    ),
]
