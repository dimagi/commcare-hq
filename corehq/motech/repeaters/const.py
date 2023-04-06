from datetime import timedelta
from django.utils.translation import gettext_lazy as _

from django.conf import settings

MAX_RETRY_WAIT = timedelta(days=7)
MIN_RETRY_WAIT = timedelta(minutes=60)
CHECK_REPEATERS_INTERVAL = timedelta(minutes=5)
CHECK_REPEATERS_PARTITION_COUNT = settings.CHECK_REPEATERS_PARTITION_COUNT
CHECK_REPEATERS_KEY = 'check-repeaters-key'
# Number of attempts to an online endpoint before cancelling payload
MAX_ATTEMPTS = 3
# Number of exponential backoff attempts to an offline endpoint
MAX_BACKOFF_ATTEMPTS = 6
# Limit the number of records to forward at a time so that one repeater
# can't hold up the rest.
RECORDS_AT_A_TIME = 1000

RECORD_PENDING_STATE = 'PENDING'
RECORD_SUCCESS_STATE = 'SUCCESS'
RECORD_FAILURE_STATE = 'FAIL'
RECORD_CANCELLED_STATE = 'CANCELLED'
RECORD_EMPTY_STATE = 'EMPTY'
RECORD_STATES = [
    (RECORD_PENDING_STATE, _('Pending')),
    (RECORD_SUCCESS_STATE, _('Succeeded')),
    (RECORD_FAILURE_STATE, _('Failed')),
    (RECORD_CANCELLED_STATE, _('Cancelled')),
    (RECORD_EMPTY_STATE, _('Empty')),
]
