
# If an error still has not been processed in this number of minutes, enqueue it
# again.
PILLOW_RETRY_QUEUE_ENQUEUING_TIMEOUT = 60 * 24

# Number of minutes to wait before retrying an unsuccessful processing attempt
PILLOW_RETRY_REPROCESS_INTERVAL = 5

# Max number of processing attempts before giving up on processing the error
PILLOW_RETRY_QUEUE_MAX_PROCESSING_ATTEMPTS = 3

# After an error's total attempts exceeds this number it will only be re-attempted
# once after being reset. This is to prevent numerous retries of errors that aren't
# getting fixed
PILLOW_RETRY_MULTI_ATTEMPTS_CUTOFF = PILLOW_RETRY_QUEUE_MAX_PROCESSING_ATTEMPTS * 3
