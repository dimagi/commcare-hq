from __future__ import absolute_import
from __future__ import unicode_literals

import logging

from django.utils.translation import ugettext_lazy as _

from corehq.motech.openmrs.serializers import to_timestamp, to_name


LOG_LEVEL_CHOICES = (
    (99, 'Disable logging'),
    (logging.ERROR, 'Error'),
    (logging.INFO, 'Info'),
)

IMPORT_FREQUENCY_WEEKLY = 'weekly'
IMPORT_FREQUENCY_MONTHLY = 'monthly'
IMPORT_FREQUENCY_CHOICES = (
    (IMPORT_FREQUENCY_WEEKLY, _('Weekly')),
    (IMPORT_FREQUENCY_MONTHLY, _('Monthly')),
)

# device_id for cases added/updated by an OpenmrsImporter.
# OpenmrsImporter ID is appended to this.
OPENMRS_IMPORTER_DEVICE_ID = 'openmrs-importer-'

# XMLNS to indicate that a form was imported from OpenMRS
XMLNS_OPENMRS = 'http://commcarehq.org/openmrs-integration'

# The Location property to store the OpenMRS location UUID in
LOCATION_OPENMRS_UUID = 'openmrs_uuid'

# To match cases against their OpenMRS Person UUID, in case config (Project Settings > Data Forwarding > Forward to
# OpenMRS > Configure > Case config) "patient_identifiers", set the identifier's key to the value of
# PERSON_UUID_IDENTIFIER_TYPE_ID. e.g.::
#
#     "patient_identifiers": {
#         /* ... */
#         "uuid": {
#             "doc_type": "CaseProperty",
#             "case_property": "openmrs_uuid",
#         }
#     }
#
# To match against any other OpenMRS identifier, set the key to the UUID of the OpenMRS Identifier Type. e.g.::
#
#     "patient_identifiers": {
#         /* ... */
#         "e2b966d0-1d5f-11e0-b929-000c29ad1d07": {
#             "doc_type": "CaseProperty",
#             "case_property": "nid"
#         }
#     }
#
PERSON_UUID_IDENTIFIER_TYPE_ID = 'uuid'


# Standard OpenMRS property names, and serializers
PERSON_PROPERTIES = {
    'gender': None,
    'age': None,
    'birthdate': to_timestamp,
    'birthdateEstimated': None,
    'dead': None,
    'deathDate': to_timestamp,
    'deathdateEstimated': None,
    'causeOfDeath': None,
}
NAME_PROPERTIES = {
    'givenName': to_name,
    'familyName': to_name,
    'middleName': to_name,
    'familyName2': to_name,
    'prefix': None,
    'familyNamePrefix': None,
    'familyNameSuffix': None,
    'degree': None,
}
ADDRESS_PROPERTIES = {
    'address1': None,
    'address2': None,
    'cityVillage': None,
    'stateProvince': None,
    'country': None,
    'postalCode': None,
    'latitude': None,
    'longitude': None,
    'countyDistrict': None,
    'address3': None,
    'address4': None,
    'address5': None,
    'address6': None,
    'startDate': to_timestamp,
    'endDate': to_timestamp,
}
