from corehq.motech.openmrs.const import IMPORT_FREQUENCY_CHOICES, IMPORT_FREQUENCY_MONTHLY
from dimagi.ext.couchdbkit import (
    Document,
    IntegerProperty,
    StringProperty,
)


class OpenmrsImporter(Document):
    """
    Import cases from an OpenMRS instance using a report
    """
    domain = StringProperty()
    server_url = StringProperty()  # e.g. "http://www.example.com/openmrs"
    username = StringProperty()
    password = StringProperty()
    log_level = IntegerProperty()

    # OpenMRS UUID of the report of patients to be imported
    report_uuid = StringProperty()

    # The case type of imported cases
    case_type = StringProperty()

    # The ID of the owner of imported cases
    owner_id = StringProperty()

    # How often should cases be imported
    import_frequency = StringProperty(choices=IMPORT_FREQUENCY_CHOICES, default=IMPORT_FREQUENCY_MONTHLY)

    # TODO: location_id
