import re
from datetime import datetime

from memoized import memoized

from dimagi.ext.couchdbkit import (
    DictProperty,
    Document,
    DocumentSchema,
    IntegerProperty,
    ListProperty,
    StringListProperty,
    StringProperty,
)

from corehq.motech.openmrs.const import (
    IMPORT_FREQUENCY_CHOICES,
    IMPORT_FREQUENCY_DAILY,
    IMPORT_FREQUENCY_MONTHLY,
    IMPORT_FREQUENCY_WEEKLY,
)
from corehq.util.timezones.utils import (
    coerce_timezone_value,
    get_timezone_for_domain,
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


class OpenmrsImporter(Document):
    """
    Import cases from an OpenMRS instance using a report
    """
    domain = StringProperty()
    server_url = StringProperty()  # e.g. "http://www.example.com/openmrs"
    username = StringProperty()
    password = StringProperty()

    notify_addresses_str = StringProperty()

    # If a domain has multiple OpenmrsImporter instances, for which CommCare location is this one authoritative?
    location_id = StringProperty()

    # How often should cases be imported
    import_frequency = StringProperty(choices=IMPORT_FREQUENCY_CHOICES, default=IMPORT_FREQUENCY_MONTHLY)

    log_level = IntegerProperty()

    # Timezone name. If not specified, the domain's timezone will be used.
    timezone = StringProperty()

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

    @property
    def notify_addresses(self):
        return [addr for addr in re.split('[, ]+', self.notify_addresses_str) if addr]

    @memoized
    def get_timezone(self):
        if self.timezone:
            return coerce_timezone_value(self.timezone)
        else:
            return get_timezone_for_domain(self.domain)

    def should_import_today(self):
        today = datetime.today()
        return (
            self.import_frequency == IMPORT_FREQUENCY_DAILY
            or (
                self.import_frequency == IMPORT_FREQUENCY_WEEKLY
                and today.weekday() == 1  # Tuesday
            )
            or (
                self.import_frequency == IMPORT_FREQUENCY_MONTHLY
                and today.day == 1
            )
        )
