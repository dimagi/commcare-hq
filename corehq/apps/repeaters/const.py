from datetime import timedelta


MAX_RETRY_WAIT = timedelta(days=1)
MIN_RETRY_WAIT = timedelta(minutes=60)
CHECK_REPEATERS_INTERVAL = timedelta(minutes=5)

RECORDS_IN_PROGRESS_REDIS_KEY = 'repeat-records-in-progress'

RECORD_PENDING_STATE = 'PENDING'
RECORD_SUCCESS_STATE = 'SUCCESS'
RECORD_FAILURE_STATE = 'FAIL'
