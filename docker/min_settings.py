# Settings for CommCare HQ containers that do not need dev or test
# requirements.

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'commcarehq',
        'USER': 'commcarehq',
        'PASSWORD': 'commcarehq',
        'HOST': 'postgres',
        'PORT': '5432',
        'TEST': {
            'SERIALIZE': False,
        },
    },
}

USE_PARTITIONED_DATABASE = False

####### Couch Config ###### noqa: E266
COUCH_DATABASES = {
    'default': {
        # for production this ought to be set to true on your configured couch instance
        'COUCH_HTTPS': False,
        'COUCH_SERVER_ROOT': 'couch:5984',  # 6984 for https couch
        'COUCH_USERNAME': '',
        'COUCH_PASSWORD': '',
        'COUCH_DATABASE_NAME': 'commcarehq'
    }
}

redis_host = 'redis'

redis_cache = {
    'BACKEND': 'django_redis.cache.RedisCache',
    'LOCATION': 'redis://{}:6379/0'.format(redis_host),
    # match production settings
    'PARSER_CLASS': 'redis.connection.HiredisParser',
    'REDIS_CLIENT_KWARGS': {
        'health_check_interval': 15,
    },
    # see `settingshelper.update_redis_location_for_tests`
    'TEST_LOCATION': 'redis://{}:6379/1'.format(redis_host),
}

CACHES = {
    'default': redis_cache,
    'redis': redis_cache
}

WS4REDIS_CONNECTION = {
    'host': redis_host,
}

ELASTICSEARCH_HOST = 'elasticsearch5'
ELASTICSEARCH_PORT = 9200  # ES 5 port
ELASTICSEARCH_MAJOR_VERSION = 5

if os.environ.get('ELASTICSEARCH_MAJOR_VERSION'):
    ELASTICSEARCH_MAJOR_VERSION = int(os.environ.get('ELASTICSEARCH_MAJOR_VERSION'))

S3_BLOB_DB_SETTINGS = {
    "url": "http://minio:9980/",
    "access_key": "admin-key",
    "secret_key": "admin-secret",
    "config": {
        "connect_timeout": 3,
        "read_timeout": 5,
        "signature_version": "s3"
    },
}

KAFKA_BROKERS = ['kafka:9092']

SHARED_DRIVE_ROOT = '/sharedfiles'

ALLOWED_HOSTS = ['*']

CELERY_BROKER_URL = 'redis://redis:6379/0'
CELERY_TASK_ALWAYS_EAGER = True
CELERY_EAGER_PROPAGATES_EXCEPTIONS = True
INACTIVITY_TIMEOUT = 60 * 24 * 365

BASE_ADDRESS = '{}:8000'.format(os.environ.get('HQ_PORT_8000_TCP_ADDR', 'localhost'))

# ####### Email setup ########

EMAIL_LOGIN = "notifications@example.com"
EMAIL_PASSWORD = "******"
EMAIL_SMTP_HOST = "smtp.example.com"
EMAIL_SMTP_PORT = 587
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ###### Bitly ########

BITLY_OAUTH_TOKEN = None

SECRET_KEY = 'you should really change this'

LOG_HOME = os.path.join(BASE_DIR, 'log')
COUCH_LOG_FILE = os.path.join(LOG_HOME, "commcarehq.couch.log")
DJANGO_LOG_FILE = os.path.join(LOG_HOME, "commcarehq.django.log")
ACCOUNTING_LOG_FILE = os.path.join(LOG_HOME, "commcarehq.accounting.log")
ANALYTICS_LOG_FILE = os.path.join(LOG_HOME, "commcarehq.analytics.log")
FORMPLAYER_TIMING_FILE = os.path.join(LOG_HOME, "formplayer.timing.log")
FORMPLAYER_DIFF_FILE = os.path.join(LOG_HOME, "formplayer.diff.log")
SOFT_ASSERTS_LOG_FILE = os.path.join(LOG_HOME, "soft_asserts.log")
MAIN_COUCH_SQL_DATAMIGRATION = os.path.join(LOG_HOME, "main_couch_sql_datamigration.log")

LOCAL_LOGGING_CONFIG = {
    'loggers': {
        '': {
            'level': 'ERROR',
            'handler': 'console',
            'propagate': False,
        },
        'django': {
            'handler': 'console',
            'level': 'ERROR',
            'propagate': False,
        },
        'notify': {
            'level': 'ERROR',
            'handler': 'console',
            'propagate': False,
        },
        'kafka': {
            'level': 'ERROR',
            'handler': 'console',
            'propagate': False,
        },
        'commcare_auth': {
            'level': 'ERROR',
            'handler': 'console',
            'propagate': False,
        }
    }
}

PHONE_TIMEZONES_HAVE_BEEN_PROCESSED = True
PHONE_TIMEZONES_SHOULD_BE_PROCESSED = True

ENABLE_PRELOGIN_SITE = True

TESTS_SHOULD_TRACK_CLEANLINESS = True

# touchforms must be running when this is false or not set
# see also corehq.apps.sms.tests.util.TouchformsTestCase
SKIP_TOUCHFORMS_TESTS = True

PILLOWTOP_MACHINE_ID = 'testhq'

CACHE_REPORTS = True

UNIT_TESTING = False
ADMINS = (('Admin', 'admin@example.com'),)

COMPRESS_OFFLINE = False

FORMPLAYER_URL = 'http://formplayer:8080'
FORMPLAYER_URL_WEBAPPS = 'http://localhost:8080'
FORMPLAYER_INTERNAL_AUTH_KEY = "secretkey"

CCHQ_API_THROTTLE_REQUESTS = 200
CCHQ_API_THROTTLE_TIMEFRAME = 10

RESTORE_PAYLOAD_DIR_NAME = 'restore'
SHARED_TEMP_DIR_NAME = 'temp'

BIGCOUCH = True

REPORTING_DATABASES = {
    'default': 'default',
    'ucr': 'default',
    'aaa-data': 'default',
}
