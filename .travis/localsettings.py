import os

####### Configuration for CommCareHQ Running on Travis-CI #####

from docker.dockersettings import *

USE_PARTITIONED_DATABASE = os.environ.get('USE_PARTITIONED_DATABASE', 'no') == 'yes'
PARTITION_DATABASE_CONFIG = get_partitioned_database_config(USE_PARTITIONED_DATABASE)

BASE_ADDRESS = '{}:8000'.format(os.environ.get('WEB_TEST_PORT_8000_TCP_ADDR', 'localhost'))

####### S3 mock server config ######
S3_BLOB_DB_SETTINGS = {"url": "http://localhost:5000"}

KAFKA_URL = 'kafka:9092'

######## Email setup ########
# email settings: these ones are the custom hq ones
EMAIL_LOGIN = "notifications@dimagi.com"
EMAIL_PASSWORD = "******"
EMAIL_SMTP_HOST = "smtp.gmail.com"
EMAIL_SMTP_PORT = 587
EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend'

####### Bitly ########

BITLY_LOGIN = None

####### Jar signing config ########

_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
JAR_SIGN = dict(
    jad_tool = os.path.join(_ROOT_DIR, "corehq", "apps", "app_manager", "JadTool.jar"),
    key_store = os.path.join(_ROOT_DIR, "InsecureTestingKeyStore"),
    key_alias = "javarosakey",
    store_pass = "onetwothreefourfive",
    key_pass = "onetwothreefourfive",
)

AUDIT_MODEL_SAVE = ['django.contrib.auth.models.User']

AUDIT_ADMIN_VIEWS = False

SECRET_KEY = 'secrettravis'

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

ELASTICSEARCH_VERSION = 1.7
