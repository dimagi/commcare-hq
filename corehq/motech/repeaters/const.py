from datetime import timedelta
from django.utils.translation import gettext_lazy as _

MAX_RETRY_WAIT = timedelta(days=7)
MIN_RETRY_WAIT = timedelta(minutes=60)
CHECK_REPEATERS_INTERVAL = timedelta(minutes=5)
CHECK_REPEATERS_KEY = 'check-repeaters-key'

RECORD_PENDING_STATE = 'PENDING'
RECORD_SUCCESS_STATE = 'SUCCESS'
RECORD_FAILURE_STATE = 'FAIL'
RECORD_CANCELLED_STATE = 'CANCELLED'
RECORD_STATES = [
    (RECORD_PENDING_STATE, _('Pending')),
    (RECORD_SUCCESS_STATE, _('Succeeded')),
    (RECORD_FAILURE_STATE, _('Failed')),
    (RECORD_CANCELLED_STATE, _('Cancelled')),
]
