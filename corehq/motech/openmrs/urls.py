from django.urls import re_path as url

from corehq.motech.openmrs.views import (
    OpenmrsImporterView,
    openmrs_import_now,
    openmrs_patient_identifier_types,
    openmrs_person_attribute_types,
    openmrs_raw_api,
    openmrs_test_fire,
)

urlpatterns = [
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
