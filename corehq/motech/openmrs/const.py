import logging
from itertools import chain

from django.utils.translation import ugettext_lazy as _

LOG_LEVEL_CHOICES = (
    (99, 'Disable logging'),
    (logging.ERROR, 'Error'),
    (logging.INFO, 'Info'),
)

IMPORT_FREQUENCY_DAILY = 'daily'
IMPORT_FREQUENCY_WEEKLY = 'weekly'
IMPORT_FREQUENCY_MONTHLY = 'monthly'
IMPORT_FREQUENCY_CHOICES = (
    (IMPORT_FREQUENCY_DAILY, _('Daily')),
    (IMPORT_FREQUENCY_WEEKLY, _('Weekly')),
    (IMPORT_FREQUENCY_MONTHLY, _('Monthly')),
)

# device_id for cases added/updated by an OpenmrsImporter.
# OpenmrsImporter ID is appended to this.
OPENMRS_IMPORTER_DEVICE_ID_PREFIX = 'openmrs-importer-'

# XMLNS to indicate that a form was imported from OpenMRS
XMLNS_OPENMRS = 'http://commcarehq.org/openmrs-integration'

OPENMRS_ATOM_FEED_POLL_INTERVAL = {'minute': '*/10'}

# device_id for cases added/updated from OpenMRS Atom feed.
# OpenmrsRepeater ID is appended to this.
OPENMRS_ATOM_FEED_DEVICE_ID = 'openmrs-atomfeed-'

ATOM_FEED_NAME_PATIENT = 'patient'
ATOM_FEED_NAME_ENCOUNTER = 'encounter'
ATOM_FEED_NAMES = (
    ATOM_FEED_NAME_PATIENT,
    ATOM_FEED_NAME_ENCOUNTER,
)

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

# A subset of OpenMRS concept data types. Omitted data types ("Coded",
# "N/A", "Document", "Rule", "Structured Numeric", "Complex") are not
# currently relevant to CommCare integration
OPENMRS_DATA_TYPE_NUMERIC = 'omrs_numeric'
OPENMRS_DATA_TYPE_TEXT = 'omrs_text'
OPENMRS_DATA_TYPE_DATE = 'omrs_date'
OPENMRS_DATA_TYPE_TIME = 'omrs_time'
OPENMRS_DATA_TYPE_DATETIME = 'omrs_datetime'
OPENMRS_DATA_TYPE_BOOLEAN = 'omrs_boolean'
OPENMRS_DATA_TYPES = (
    OPENMRS_DATA_TYPE_NUMERIC,
    OPENMRS_DATA_TYPE_TEXT,
    OPENMRS_DATA_TYPE_DATE,
    OPENMRS_DATA_TYPE_TIME,
    OPENMRS_DATA_TYPE_DATETIME,
    OPENMRS_DATA_TYPE_BOOLEAN,
)

# Standard OpenMRS property names and their data types
PERSON_PROPERTIES = {
    'gender': OPENMRS_DATA_TYPE_TEXT,
    'age': OPENMRS_DATA_TYPE_NUMERIC,
    'birthdate': OPENMRS_DATA_TYPE_DATETIME,
    'birthdateEstimated': OPENMRS_DATA_TYPE_BOOLEAN,
    'dead': OPENMRS_DATA_TYPE_BOOLEAN,
    'deathDate': OPENMRS_DATA_TYPE_DATETIME,
    'deathdateEstimated': OPENMRS_DATA_TYPE_BOOLEAN,
    'causeOfDeath': OPENMRS_DATA_TYPE_TEXT,
}
NAME_PROPERTIES = {
    'givenName': OPENMRS_DATA_TYPE_TEXT,
    'familyName': OPENMRS_DATA_TYPE_TEXT,
    'middleName': OPENMRS_DATA_TYPE_TEXT,
    'familyName2': OPENMRS_DATA_TYPE_TEXT,
    'prefix': OPENMRS_DATA_TYPE_TEXT,
    'familyNamePrefix': OPENMRS_DATA_TYPE_TEXT,
    'familyNameSuffix': OPENMRS_DATA_TYPE_TEXT,
    'degree': OPENMRS_DATA_TYPE_TEXT,
}
ADDRESS_PROPERTIES = {
    'address1': OPENMRS_DATA_TYPE_TEXT,
    'address2': OPENMRS_DATA_TYPE_TEXT,
    'cityVillage': OPENMRS_DATA_TYPE_TEXT,
    'stateProvince': OPENMRS_DATA_TYPE_TEXT,
    'country': OPENMRS_DATA_TYPE_TEXT,
    'postalCode': OPENMRS_DATA_TYPE_TEXT,
    'latitude': OPENMRS_DATA_TYPE_NUMERIC,
    'longitude': OPENMRS_DATA_TYPE_NUMERIC,
    'countyDistrict': OPENMRS_DATA_TYPE_TEXT,
    'address3': OPENMRS_DATA_TYPE_TEXT,
    'address4': OPENMRS_DATA_TYPE_TEXT,
    'address5': OPENMRS_DATA_TYPE_TEXT,
    'address6': OPENMRS_DATA_TYPE_TEXT,
    'startDate': OPENMRS_DATA_TYPE_DATETIME,
    'endDate': OPENMRS_DATA_TYPE_DATETIME,
}
OPENMRS_PROPERTIES = dict(chain(
    PERSON_PROPERTIES.items(),
    NAME_PROPERTIES.items(),
    ADDRESS_PROPERTIES.items(),
))
