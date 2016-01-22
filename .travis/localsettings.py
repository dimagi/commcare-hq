import os

####### Configuration for CommCareHQ Running on Travis-CI #####

BASE_ADDRESS = '127.0.0.1:8000'

####### Database config. This assumes Postgres ####### 
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'commcarehq',
        'USER': 'postgres',
        'PASSWORD': '',
        'HOST': 'localhost',
        'PORT': '5432',
        'TEST': {
            'SERIALIZE': False,  # https://docs.djangoproject.com/en/1.8/ref/settings/#serialize
        },
    }
}

####### Couch Config ######
COUCH_HTTPS = False
COUCH_SERVER_ROOT = '127.0.0.1:5984'
COUCH_USERNAME = ''
COUCH_PASSWORD = ''
COUCH_DATABASE_NAME = 'commcarehq'

####### S3 mock server config ######
# See also utils.sh setup_moto_s3_server
S3_BLOB_DB_SETTINGS = {"url": "http://localhost:5000"}

######## Email setup ########
# email settings: these ones are the custom hq ones
EMAIL_LOGIN = "notifications@dimagi.com"
EMAIL_PASSWORD = "******"
EMAIL_SMTP_HOST = "smtp.gmail.com"
EMAIL_SMTP_PORT = 587
EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend'

####### Bitly ########

BITLY_LOGIN = None
BITLY_APIKEY = '*******'

####### Jar signing config ########

_ROOT_DIR  = os.path.dirname(os.path.abspath(__file__))
JAR_SIGN = dict(
    jad_tool = os.path.join(_ROOT_DIR, "corehq", "apps", "app_manager", "JadTool.jar"),
    key_store = os.path.join(_ROOT_DIR, "InsecureTestingKeyStore"),
    key_alias = "javarosakey",
    store_pass = "onetwothreefourfive",
    key_pass = "onetwothreefourfive",
)

# soil settings
SOIL_DEFAULT_CACHE = "redis"

redis_cache = {
    'BACKEND': 'django_redis.cache.RedisCache',
    'LOCATION': 'redis://127.0.0.1:6379/0',
    'OPTIONS': {},
}
CACHES = {
    'default': redis_cache,
    'redis': redis_cache,
}

AUDIT_MODEL_SAVE = ['django.contrib.auth.models.User']

ELASTICSEARCH_HOST = 'localhost' 
ELASTICSEARCH_PORT = 9200

AUDIT_ADMIN_VIEWS=False

SECRET_KEY='secrettravis'

# No logging
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
        },
        'south': {
            'level': 'CRITICAL',
            'handler': 'null',
            'propagate': False,
        },
        'pillowtop': {
            'level': 'CRITICAL',
            'handler': 'null',
            'propagate': False,
        }
    }
}

SOUTH_TESTS_MIGRATE = True
PHONE_TIMEZONES_HAVE_BEEN_PROCESSED = True
PHONE_TIMEZONES_SHOULD_BE_PROCESSED = True


ENABLE_PRELOGIN_SITE = True

TESTS_SHOULD_TRACK_CLEANLINESS = True

UNIT_TESTING = True

LOCAL_APPS = (
    'testapps.test_elasticsearch',
    'testapps.test_pillowtop',
)

PILLOWTOP_MACHINE_ID = 'testhq'
ALLOW_ELASTICSEARCH_TESTS = True
