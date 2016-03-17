from datetime import timedelta


MAX_RETRY_WAIT = timedelta(days=3)
MIN_RETRY_WAIT = timedelta(minutes=60)
CHECK_REPEATERS_INTERVAL = timedelta(minutes=5)
CHECK_REPEATERS_KEY = 'check-repeaters-key'

POST_TIMEOUT = 45  # seconds
SIMPLE_POST_CACHED_PREFIX = 'repeater_cached_post:'

RECORD_PENDING_STATE = 'PENDING'
RECORD_SUCCESS_STATE = 'SUCCESS'
RECORD_FAILURE_STATE = 'FAIL'
