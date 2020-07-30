####### Configuration for CommCareHQ Running in docker #######


import os

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

USE_PARTITIONED_DATABASE = os.environ.get('USE_PARTITIONED_DATABASE', 'no') == 'yes'
if USE_PARTITIONED_DATABASE:
    DATABASES.update({
        'proxy': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'commcarehq_proxy',
            'USER': 'commcarehq',
            'PASSWORD': 'commcarehq',
            'HOST': 'postgres',
            'PORT': '5432',
            'TEST': {
                'SERIALIZE': False,
            },
            'PLPROXY': {
                'PROXY': True,
                'PLPROXY_HOST': 'localhost'
            }
        },
        'p1': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'commcarehq_p1',
            'USER': 'commcarehq',
            'PASSWORD': 'commcarehq',
            'HOST': 'postgres',
            'PORT': '5432',
            'TEST': {
                'SERIALIZE': False,
            },
            'PLPROXY': {
                'SHARDS': [0, 1],
            }
        },
        'p2': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'commcarehq_p2',
            'USER': 'commcarehq',
            'PASSWORD': 'commcarehq',
            'HOST': 'postgres',
            'PORT': '5432',
            'TEST': {
                'SERIALIZE': False,
            },
            'PLPROXY': {
                'SHARDS': [2, 3],
            }
        },
    })

# See CITUSDB_SETUP.md for explanation
DATABASES.update({
    'icds-ucr': {
        'ENGINE': 'django.db.backends.postgresql',
        'DISABLE_SERVER_SIDE_CURSORS': True,
        'NAME': 'commcare_ucr_citus',
        'USER': 'commcarehq',
        'PASSWORD': 'commcarehq',
        'HOST': 'citus_master',
        'PORT': '5432',
        'TEST': {
            'SERIALIZE': False,
        },
    },
})

ICDS_USE_CITUS = True

####### Couch Config ######
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
}

CACHES = {
    'default': redis_cache,
    'redis': redis_cache
}

WS4REDIS_CONNECTION = {
    'host': redis_host,
}

ELASTICSEARCH_HOST = 'elasticsearch'
ELASTICSEARCH_PORT = 6200
ELASTICSEARCH_MAJOR_VERSION = 2
# to enable v2 ES tests
if os.environ.get('ELASTICSEARCH_2_PORT'):
    ELASTICSEARCH_HOST = 'elasticsearch2'
    ELASTICSEARCH_PORT = int(os.environ.get('ELASTICSEARCH_2_PORT'))

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
#FIX_LOGGER_ERROR_OBFUSCATION = True

# faster compressor that doesn't do source maps
COMPRESS_JS_COMPRESSOR = 'compressor.js.JsCompressor'
CELERY_TASK_ALWAYS_EAGER = True
CELERY_EAGER_PROPAGATES_EXCEPTIONS = True
INACTIVITY_TIMEOUT = 60 * 24 * 365
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

BITLY_OAUTH_TOKEN = None

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
LOCAL_LOGGING_CONFIG = {
    'handlers': {
        'null': {
            'level': 'DEBUG',
            'class': 'logging.NullHandler',
        }
    },
    'loggers': {
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

CACHE_REPORTS = True

if os.environ.get("COMMCAREHQ_BOOTSTRAP") == "yes":
    UNIT_TESTING = False
    ADMINS = (('Admin', 'admin@example.com'),)

    COMPRESS_OFFLINE = False

    FORMPLAYER_URL = 'http://formplayer:8010'

    CCHQ_API_THROTTLE_REQUESTS = 200
    CCHQ_API_THROTTLE_TIMEFRAME = 10

    RESTORE_PAYLOAD_DIR_NAME = 'restore'
    SHARED_TEMP_DIR_NAME = 'temp'

BIGCOUCH = True

LOCAL_APPS = (
    # these are necessary to facilitate ICDS tests
    "custom.icds",
    "custom.icds.data_management",
    "custom.icds_reports",
)

REPORTING_DATABASES = {
    'default': 'default',
    'ucr': 'default',
    'aaa-data': 'default',
    'icds-ucr-citus': 'icds-ucr',
}
