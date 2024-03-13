from datetime import timedelta
from django.utils.translation import gettext_lazy as _

from django.conf import settings
from django.db.models import IntegerChoices

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


class State(IntegerChoices):
    # powers of two to allow multiple simultaneous states (not currently used)
    Pending = 1, _('Pending')
    Fail = 2, _('Failed')
    Success = 4, _('Succeeded')
    Cancelled = 8, _('Cancelled')
    Empty = 16, _('Empty')


RECORD_PENDING_STATE = State.Pending
RECORD_SUCCESS_STATE = State.Success
RECORD_FAILURE_STATE = State.Fail
RECORD_CANCELLED_STATE = State.Cancelled
RECORD_EMPTY_STATE = State.Empty
COUCH_STATES = {
    State.Pending: 'PENDING',
    State.Fail: 'FAIL',
    State.Success: 'SUCCESS',
    State.Cancelled: 'CANCELLED',
    State.Empty: 'EMPTY',  # Not used in Couch, grouped with SUCCESS?
}
