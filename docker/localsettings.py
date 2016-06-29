####### Configuration for CommCareHQ Running in docker #######

import os

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
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

USE_PARTITIONED_DATABASE = os.environ.get('USE_PARTITIONED_DATABASE', 'no') == 'yes'
if USE_PARTITIONED_DATABASE:
    DATABASES.update({
        'proxy': {
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'NAME': 'commcarehq_proxy',
            'USER': 'commcarehq',
            'PASSWORD': 'commcarehq',
            'HOST': 'postgres',
            'PORT': '5432',
            'TEST': {
                'SERIALIZE': False,
            },
        },
        'p1': {
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'NAME': 'commcarehq_p1',
            'USER': 'commcarehq',
            'PASSWORD': 'commcarehq',
            'HOST': 'postgres',
            'PORT': '5432',
            'TEST': {
                'SERIALIZE': False,
            },
        },
        'p2': {
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'NAME': 'commcarehq_p2',
            'USER': 'commcarehq',
            'PASSWORD': 'commcarehq',
            'HOST': 'postgres',
            'PORT': '5432',
            'TEST': {
                'SERIALIZE': False,
            },
        },
    })

    PARTITION_DATABASE_CONFIG = {
        'shards': {
            'p1': [0, 1],
            'p2': [2, 3]
        },
        'groups': {
            'main': ['default'],
            'proxy': ['proxy'],
            'form_processing': ['p1', 'p2'],
        },
        'host_map': {
            'postgres': 'localhost'
        }
    }

####### Couch Config ######
COUCH_HTTPS = False
COUCH_SERVER_ROOT = 'couch:5984'
COUCH_USERNAME = ''
COUCH_PASSWORD = ''
COUCH_DATABASE_NAME = 'commcarehq'

redis_cache = {
    'BACKEND': 'django_redis.cache.RedisCache',
    'LOCATION': 'redis://redis:6379/0',
    'OPTIONS': {},
}
CACHES = {
    'default': redis_cache,
    'redis': redis_cache
}

ELASTICSEARCH_HOST = 'elasticsearch'
ELASTICSEARCH_PORT = 9200

S3_BLOB_DB_SETTINGS = {
    "url": "http://riakcs:9980/",
    "access_key": "admin-key",
    "secret_key": "admin-secret",
    "config": {"connect_timeout": 3, "read_timeout": 5},
}

KAFKA_URL = 'kafka:9092'

SHARED_DRIVE_ROOT = '/sharedfiles'

ALLOWED_HOSTS = ['*']
#FIX_LOGGER_ERROR_OBFUSCATION = True

# faster compressor that doesn't do source maps
COMPRESS_JS_COMPRESSOR = 'compressor.js.JsCompressor'
CELERY_ALWAYS_EAGER = True
CELERY_EAGER_PROPAGATES_EXCEPTIONS = True
INACTIVITY_TIMEOUT = 60 * 24 * 365
CSRF_SOFT_MODE = False
SHARED_DRIVE_ROOT = '/sharedfiles'

BASE_ADDRESS = '{}:8000'.format(os.environ.get('HQ_PORT_8000_TCP_ADDR', 'localhost'))

######## Email setup ########
# email settings: these ones are the custom hq ones
EMAIL_LOGIN = "notifications@dimagi.com"
EMAIL_PASSWORD = "******"
EMAIL_SMTP_HOST = "smtp.gmail.com"
EMAIL_SMTP_PORT = 587
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

####### Bitly ########

BITLY_LOGIN = None

####### Jar signing config ########

_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
JAR_SIGN = {
    "jad_tool": os.path.join(_ROOT_DIR, "corehq", "apps", "app_manager", "JadTool.jar"),
    "key_store": os.path.join(_ROOT_DIR, "InsecureTestingKeyStore"),
    "key_alias": "javarosakey",
    "store_pass": "onetwothreefourfive",
    "key_pass": "onetwothreefourfive",
}

AUDIT_MODEL_SAVE = ['django.contrib.auth.models.User']

AUDIT_ADMIN_VIEWS = False

SECRET_KEY = 'secrettravis'

# No logging
LOCAL_LOGGING_HANDLERS = {
    'null': {
        'level': 'DEBUG',
        'class': 'django.utils.log.NullHandler',
    },
}

LOCAL_LOGGING_LOGGERS = {
    '': {
        'level': 'CRITICAL',
        'handler': 'null',
        'propagate': True,
    },
    'pillowtop': {
        'level': 'CRITICAL',
        'handler': 'null',
        'propagate': True,
    },
    'notify': {
        'level': 'CRITICAL',
        'handler': 'null',
        'propagate': True,
    },
}


PHONE_TIMEZONES_HAVE_BEEN_PROCESSED = True
PHONE_TIMEZONES_SHOULD_BE_PROCESSED = True

ENABLE_PRELOGIN_SITE = True

TESTS_SHOULD_TRACK_CLEANLINESS = True

# touchforms must be running when this is false or not set
# see also corehq.apps.sms.tests.util.TouchformsTestCase
SKIP_TOUCHFORMS_TESTS = True

UNIT_TESTING = True

PILLOWTOP_MACHINE_ID = 'testhq'

ELASTICSEARCH_VERSION = 1.7

CACHE_REPORTS = True

if os.environ.get("COMMCAREHQ_BOOTSTRAP") == "yes":
    UNIT_TESTING = False
    ADMINS = (('Admin', 'admin@example.com'),)

    CELERY_SEND_TASK_ERROR_EMAILS = True

    LESS_DEBUG = True
    LESS_WATCH = False
    COMPRESS_OFFLINE = False

    XFORMS_PLAYER_URL = 'http://127.0.0.1:4444'

    TOUCHFORMS_API_USER = 'admin@example.com'
    TOUCHFORMS_API_PASSWORD = 'password'

    CCHQ_API_THROTTLE_REQUESTS = 200
    CCHQ_API_THROTTLE_TIMEFRAME = 10

    RESTORE_PAYLOAD_DIR_NAME = 'restore'
    SHARED_TEMP_DIR_NAME = 'temp'
