from __future__ import absolute_import
from __future__ import unicode_literals
from django.utils.encoding import python_2_unicode_compatible
from corehq.motech.openmrs.const import IMPORT_FREQUENCY_CHOICES, IMPORT_FREQUENCY_MONTHLY
from dimagi.ext.couchdbkit import (
    Document,
    IntegerProperty,
    StringProperty,
    DictProperty,
    ListProperty,
    DocumentSchema,
)


# Supported values for ColumnMapping.data_type
# ColumnMapping.data_type is only required if json.loads returns the wrong value
POSIX_MILLISECONDS = 'posix_milliseconds'
DATA_TYPES = (
    POSIX_MILLISECONDS,
)


class ColumnMapping(DocumentSchema):
    column = StringProperty()
    property = StringProperty()
    data_type = StringProperty(choices=DATA_TYPES, required=False)


@python_2_unicode_compatible
class OpenmrsImporter(Document):
    """
    Import cases from an OpenMRS instance using a report
    """
    domain = StringProperty()
    server_url = StringProperty()  # e.g. "http://www.example.com/openmrs"
    username = StringProperty()
    password = StringProperty()

    # If a domain has multiple OpenmrsImporter instances, for which CommCare location is this one authoritative?
    location_id = StringProperty()

    # How often should cases be imported
    import_frequency = StringProperty(choices=IMPORT_FREQUENCY_CHOICES, default=IMPORT_FREQUENCY_MONTHLY)

    log_level = IntegerProperty()

    # OpenMRS UUID of the report of patients to be imported
    report_uuid = StringProperty()

    # Can include template params, e.g. {"endDate": "{{ today }}"}
    # Available template params: "today", "location"
    report_params = DictProperty()

    # The case type of imported cases
    case_type = StringProperty()

    # The ID of the owner of imported cases, if all imported cases are to have the same owner. To assign imported
    # cases to different owners, see `location_type` below.
    owner_id = StringProperty()

    # If report_params includes "{{ location }}" then location_type_name is used to determine which locations to
    # pull the report for. Those locations will need an "openmrs_uuid" param set. Imported cases will be owned by
    # the first mobile worker assigned to that location. If this OpenmrsImporter.location_id is set, only
    # sub-locations will be returned
    location_type_name = StringProperty()

    # external_id should always be the OpenMRS UUID of the patient (and not, for example, a national ID number)
    # because it is immutable. external_id_column is the column that contains the UUID
    external_id_column = StringProperty()

    # Space-separated column(s) to be concatenated to create the case name (e.g. "givenName familyName")
    name_columns = StringProperty()

    column_map = ListProperty(ColumnMapping)

    def __str__(self):
        return self.server_url
