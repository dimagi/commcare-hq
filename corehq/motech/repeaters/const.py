from datetime import timedelta

MAX_RETRY_WAIT = timedelta(days=7)
MIN_RETRY_WAIT = timedelta(minutes=60)
CHECK_REPEATERS_INTERVAL = timedelta(minutes=5)
CHECK_REPEATERS_KEY = 'check-repeaters-key'

RECORD_PENDING_STATE = 'PENDING'
RECORD_SUCCESS_STATE = 'SUCCESS'
RECORD_FAILURE_STATE = 'FAIL'
RECORD_CANCELLED_STATE = 'CANCELLED'

# Repeaters in the order in which they should appear in "Data Forwarding"
REPEATER_CLASSES = (
    'corehq.motech.repeaters.models.FormRepeater',
    'corehq.motech.repeaters.models.CaseRepeater',
    'corehq.motech.repeaters.models.CreateCaseRepeater',
    'corehq.motech.repeaters.models.UpdateCaseRepeater',
    'corehq.motech.repeaters.models.ReferCaseRepeater',
    'corehq.motech.repeaters.models.ShortFormRepeater',
    'corehq.motech.repeaters.models.AppStructureRepeater',
    'corehq.motech.repeaters.models.UserRepeater',
    'corehq.motech.repeaters.models.LocationRepeater',
    'corehq.motech.openmrs.repeaters.OpenmrsRepeater',
    'corehq.motech.dhis2.repeaters.Dhis2Repeater',
    'corehq.motech.dhis2.repeaters.Dhis2EntityRepeater',
    'custom.icds.repeaters.phi.SearchByParamsRepeater',
    'custom.icds.repeaters.phi.ValidatePHIDRepeater',
)
