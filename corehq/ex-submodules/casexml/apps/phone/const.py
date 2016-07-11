# how long a cached payload sits around for (in seconds).
INITIAL_SYNC_CACHE_TIMEOUT = 60 * 60  # 1 hour

# the threshold for setting a cached payload on initial sync (in seconds).
# restores that take less than this time will not be cached to allow
# for rapid iteration on fixtures/cases/etc.
INITIAL_SYNC_CACHE_THRESHOLD = 60  # 1 minute

# if a sync is happening asynchronously, we wait for this long for a result to
# initially be returned, otherwise we return a 202
INITIAL_ASYNC_TIMEOUT_THRESHOLD = 10
# The Retry-After header parameter. Ask the phone to retry in this many seconds
# to see if the task is done.
ASYNC_RETRY_AFTER = 30

ASYNC_RESTORE_CACHE_KEY_PREFIX = "async-restore-task"
RESTORE_CACHE_KEY_PREFIX = "ota-restore"
