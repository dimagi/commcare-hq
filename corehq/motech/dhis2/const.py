from django.utils.translation import gettext_lazy as _

SEND_FREQUENCY_WEEKLY = 'weekly'
SEND_FREQUENCY_MONTHLY = 'monthly'
SEND_FREQUENCY_QUARTERLY = 'quarterly'
SEND_FREQUENCY_CHOICES = [
    (SEND_FREQUENCY_WEEKLY, _('Weekly')),
    (SEND_FREQUENCY_MONTHLY, _('Monthly')),
    (SEND_FREQUENCY_QUARTERLY, _('Quarterly')),
]
SEND_FREQUENCIES = [c[0] for c in SEND_FREQUENCY_CHOICES]

# A subset of DHIS2 data types. Omitted data types:
# * COORDINATE
# * EMAIL
# * FILE_RESOURCE
# * INTEGER_NEGATIVE
# * INTEGER_POSITIVE
# * INTEGER_ZERO_OR_POSITIVE
# * LETTER
# * LONG_TEXT
# * PERCENTAGE
# * PHONE_NUMBER
# * TRUE_ONLY
# * UNIT_INTERVAL
DHIS2_DATA_TYPE_BOOLEAN = "dhis2_boolean"
DHIS2_DATA_TYPE_DATE = "dhis2_date"
DHIS2_DATA_TYPE_DATETIME = "dhis2_datetime"
DHIS2_DATA_TYPE_INTEGER = "dhis2_integer"
DHIS2_DATA_TYPE_NUMBER = "dhis2_number"
DHIS2_DATA_TYPE_TEXT = "dhis2_text"

DHIS2_EVENT_STATUS_ACTIVE = "ACTIVE"
DHIS2_EVENT_STATUS_COMPLETED = "COMPLETED"
DHIS2_EVENT_STATUS_VISITED = "VISITED"
DHIS2_EVENT_STATUS_SCHEDULED = "SCHEDULED"
DHIS2_EVENT_STATUS_OVERDUE = "OVERDUE"
DHIS2_EVENT_STATUS_SKIPPED = "SKIPPED"
DHIS2_EVENT_STATUSES = (
    DHIS2_EVENT_STATUS_ACTIVE,
    DHIS2_EVENT_STATUS_COMPLETED,
    DHIS2_EVENT_STATUS_VISITED,
    DHIS2_EVENT_STATUS_SCHEDULED,
    DHIS2_EVENT_STATUS_OVERDUE,
    DHIS2_EVENT_STATUS_SKIPPED,
)

DHIS2_PROGRAM_STATUS_ACTIVE = "ACTIVE"
DHIS2_PROGRAM_STATUS_COMPLETED = "COMPLETED"
DHIS2_PROGRAM_STATUS_CANCELLED = "CANCELLED"
DHIS2_PROGRAM_STATUSES = (
    DHIS2_PROGRAM_STATUS_ACTIVE,
    DHIS2_PROGRAM_STATUS_COMPLETED,
    DHIS2_PROGRAM_STATUS_CANCELLED,
)

LOCATION_DHIS_ID = 'dhis_id'

DHIS2_UID_RE = r'^[a-zA-Z][a-zA-Z0-9]{10}$'
DHIS2_UID_MESSAGE = _('A DHIS2 "UID" is exactly 11 alpha-numeric characters '
                      'long, and starts with a letter.')

# XMLNS to indicate that a case was updated with data from DHIS2.
# (Used for updating cases with their tracked entity instance ID.)
XMLNS_DHIS2 = 'http://commcarehq.org/dhis2-integration'

DHIS2_MAX_KNOWN_GOOD_VERSION = "2.39.0"

COMPLETE_DATE_EMPTY = "complete_date_empty"
COMPLETE_DATE_COLUMN = "complete_date_column"
COMPLETE_DATE_ON_PERIOD_END = "complete_date_on_period_end"
COMPLETE_DATE_ON_SEND = "complete_date_on_send"

COMPLETE_DATE_CHOICES = [
    (COMPLETE_DATE_EMPTY, _('None')),
    (COMPLETE_DATE_COLUMN, _('UCR column')),
    (COMPLETE_DATE_ON_PERIOD_END, _('Use last day of period')),
    (COMPLETE_DATE_ON_SEND, _('Use date that dataValues are sent')),
]

ERROR_DIAGNOSIS = {
    '504 Gateway Time-out': _(
        "It could be that CommCare HQ is sending data faster than DHIS2 can "
        "handle. If possible, try increasing the resources on your DHIS2 instance. "
        "The ability to send data from CommCare HQ slower is coming soon."
    ),
    'Event.programStage does not point to a valid programStage: null': _(
        "This Event’s Program has multiple stages. You will need to update the configuration "
        "to specify which program stage the Event’s data belongs to. "
        "(See the “programStage” property in the data forwarder’s configuration.)"
    ),
    'Program stage is not repeatable and an event already exists': _(
        "An event for this program stage has already been submitted. It could be that the new "
        "event is for a different program stage. You will need to update the configuration to "
        "specify the correct program stage for this submission. (See the “programStage” property "
        "in the data forwarder’s configuration.)"
    ),
    '502 Bad Gateway': _(
        "The DHIS2 server is currently not accepting connections."
    )
}
