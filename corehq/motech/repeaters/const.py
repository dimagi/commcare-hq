from __future__ import absolute_import
from datetime import timedelta


MAX_RETRY_WAIT = timedelta(days=7)
MIN_RETRY_WAIT = timedelta(minutes=60)
CHECK_REPEATERS_INTERVAL = timedelta(minutes=5)
CHECK_REPEATERS_KEY = 'check-repeaters-key'

POST_TIMEOUT = 75  # seconds

RECORD_PENDING_STATE = 'PENDING'  # queued to be sent
RECORD_SUCCESS_STATE = 'SUCCESS'  # sent successfully
RECORD_FAILURE_STATE = 'FAIL'  # send failed, likely still pending
RECORD_CANCELLED_STATE = 'CANCELLED'  # will need to be manually retriggered
RECORD_ARCHIVED_STATE = 'ARCHIVED'  # kept around for record-keeping only
