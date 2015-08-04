# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

SECRET_KEY = 'this is not a secret key'

INSTALLED_APPS = (
    'pillowtop',
    'pillow_retry',
    'couchdbkit.ext.django',
    'coverage',
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'south'
)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'pillowtop',
        'USER': 'postgres',
        'PASSWORD': '',
        'HOST': 'localhost',
        'PORT': '5432'
    }
}


####### Pillow Retry Queue Settings #######

# Number of minutes a celery task will alot for itself (via lock timeout)
PILLOW_RETRY_PROCESSING_LOCK_TIMEOUT = 5

# Number of minutes to wait before retrying an unsuccessful processing attempt
PILLOW_RETRY_REPROCESS_INTERVAL = 5

# Max number of processing attempts before giving up on processing the error
PILLOW_RETRY_QUEUE_MAX_PROCESSING_ATTEMPTS = 3

# The backoff factor by which to increase re-process intervals by.
# next_interval = PILLOW_RETRY_REPROCESS_INTERVAL * attempts^PILLOW_RETRY_BACKOFF_FACTOR
PILLOW_RETRY_BACKOFF_FACTOR = 2

# After an error's total attempts exceeds this number it will only be re-attempted
# once after being reset. This is to prevent numerous retries of errors that aren't
# getting fixed
PILLOW_RETRY_MULTI_ATTEMPTS_CUTOFF = PILLOW_RETRY_QUEUE_MAX_PROCESSING_ATTEMPTS * 3

####### Couch Config ######
COUCH_DATABASE = 'http://localhost:5984/pillowtop'

COUCHDB_DATABASES = [ (app, COUCH_DATABASE) for app in [
    'pillowtop',
    'pillow_retry',
    'couch',
    'ext',
    # This is necessary for abstract classes in dimagi.utils.couch.undo
    # otherwise breaks tests
]]

TEST_RUNNER = 'couchdbkit.ext.django.testrunner.CouchDbKitTestSuiteRunner'

####### # Email setup ########
# Print emails to console so there is no danger of spamming, but you can still get registration URLs
EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend'
EMAIL_LOGIN = "nobody@example.com"
EMAIL_PASSWORD = "******"
EMAIL_SMTP_HOST = "smtp.example.com"
EMAIL_SMTP_PORT = 587

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    },
    'redis': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/0',
        'OPTIONS': {},
    },
}

# Disable logging during testing
LOGGING = {
    'version': 1,
    'handlers': {
        'null': {
            'level': 'DEBUG',
            'class': 'django.utils.log.NullHandler',
        },
    },
    'loggers': {
        '': {
            'level': 'CRITICAL',
            'handler': 'null',
            'propagate': False,
        }
    }
}
