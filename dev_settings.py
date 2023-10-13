"""
This is a home for shared dev settings.  Feel free to add anything that all
devs should have set.

Add `from dev_settings import *` to the top of your localsettings file to use.
You can then override or append to any of these settings there.
"""
import os
import settingshelper

LOCAL_APPS = (
    'django_extensions',
)

# TEST_RUNNER is overridden in testsettings, which is the default settings
# module for the test command (see manage.py); this has no effect by default.
# Use ./manage.py test --settings=settings to use this setting.
TEST_RUNNER = 'testrunner.DevTestRunner'

SKIP_TESTS_REQUIRING_EXTRA_SETUP = True

# touchforms must be running when this is false or not set
# see also corehq.apps.sms.tests.util.TouchformsTestCase
SKIP_TOUCHFORMS_TESTS = True

# See comment under settings.SMS_QUEUE_ENABLED
SMS_QUEUE_ENABLED = False

# https://docs.djangoproject.com/en/1.8/ref/settings/#std:setting-TEST_NON_SERIALIZED_APPS
# https://docs.djangoproject.com/en/1.8/ref/settings/#serialize
TEST_NON_SERIALIZED_APPS = ['corehq.form_processor', 'corehq.blobs']

# Django Extensions
# These things will be imported when you run ./manage.py shell_plus
SHELL_PLUS_POST_IMPORTS = (
    # Models
    ('datetime'),
    ('corehq.apps.app_manager.models', 'Application'),
    ('corehq.apps.domain.models', 'Domain'),
    ('corehq.apps.groups.models', 'Group'),
    ('corehq.apps.users.models', ('CouchUser', 'WebUser', 'CommCareUser')),
    ('corehq.form_processor.models', ('CommCareCase', 'XFormInstance')),

    # Data querying utils
    ('dimagi.utils.couch.database', 'get_db'),
    ('corehq.apps', 'es'),
)

INTERNAL_IPS = ['127.0.0.1']
ALLOWED_HOSTS = ['*']
FIX_LOGGER_ERROR_OBFUSCATION = True
LOCAL_LOGGING_CONFIG = {
    'loggers': {
        'corehq.apps.auditcare': {
            'handlers': ['null'],
            'level': 'WARNING',
        },
        # The following configuration will print out all queries that are run through sqlalchemy on the command line
        # Useful for UCR debugging
        # 'sqlalchemy.engine': {
        #     'handlers': ['console'],
        #     'level': 'INFO',
        # },
    }
}

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'commcarehq',
        'USER': 'commcarehq',
        'PASSWORD': 'commcarehq',
        'HOST': 'localhost',
        'PORT': '5432',
        'TEST': {
            'SERIALIZE': False,
        },
    }
}

COUCH_DATABASES = {
    'default': {
        'COUCH_HTTPS': False,
        'COUCH_SERVER_ROOT': 'localhost:5984',
        'COUCH_USERNAME': 'admin',
        'COUCH_PASSWORD': 'commcarehq',
        'COUCH_DATABASE_NAME': 'commcarehq'
    },
}

redis_cache = {
    'BACKEND': 'django_redis.cache.RedisCache',
    'LOCATION': 'redis://127.0.0.1:6379/0',
    # match production settings
    'PARSER_CLASS': 'redis.connection.HiredisParser',
    'REDIS_CLIENT_KWARGS': {
        'health_check_interval': 15,
    },
    # see `settingshelper.update_redis_location_for_tests`
    'TEST_LOCATION': 'redis://127.0.0.1:6379/1',
}

CACHES = {
    'default': redis_cache,
    'redis': redis_cache,
}

PILLOWTOP_MACHINE_ID = 'testhq'  # for tests

#  make celery synchronous
CELERY_TASK_ALWAYS_EAGER = True
# Fail hard in tasks so you get a traceback
CELERY_EAGER_PROPAGATES_EXCEPTIONS = True

# default inactivity timeout to 1 year
INACTIVITY_TIMEOUT = 60 * 24 * 365

CACHE_REPORTS = False

# Make a dir to use for storing attachments as blobs on the filesystem
shared_dirname = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                              'sharedfiles')
if not os.path.exists(shared_dirname):
    os.mkdir(shared_dirname)
SHARED_DRIVE_ROOT = shared_dirname

PHONE_TIMEZONES_SHOULD_BE_PROCESSED = True

# These ES hosts are to be used strictly for DEBUG mode read operations
ELASTICSEARCH_DEBUG_HOSTS = {
    'prod': '10.202.40.116',
    'staging': '10.201.40.161',
    'india': '10.162.36.221',
    'icds': '100.71.184.7',
}

# The default settings for Elasticsearch replicas and shards are managed
# in `corehq/apps/es/index/settings.py`. These values are not
# appropriate for dev environments, where there is only one node and so
# replicas can't be allocated, and where indexed data is unlikely to
# exceed 20GB, which is the recommended size per shard. The following
# sets minimum values for all Elasticsearch indices:
ES_SETTINGS = {
    'default': {
        'number_of_replicas': 0,
        'number_of_shards': 1,
    },

    # If the space used by a shard is more than 20GB then you can
    # increase the number of shards for a specific index
    # (e.g. "case_search") by uncommenting and adapting the following:
    #
    # 'case_search': {
    #     'number_of_replicas': 0,
    #     'number_of_shards': 2,
    # }
    #
    # [elasticsearch-head](https://github.com/mobz/elasticsearch-head)
    # can show you how much space an index is using.
}

FORMPLAYER_INTERNAL_AUTH_KEY = "secretkey"

# use console email by default
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

if settingshelper.is_testing():
    S3_BLOB_DB_SETTINGS = {
        "url": "http://localhost:9980",
        "access_key": "admin-key",
        "secret_key": "admin-secret",
        "config": {
            "connect_timeout": 3,
            "read_timeout": 5,
            "signature_version": "s3"
        },
    }

# substantially increase the API request limits in dev, in part
# to prevent AssertionError: 429 != 200  test failures
CCHQ_API_THROTTLE_REQUESTS = 200  # number of requests allowed per timeframe
CCHQ_API_THROTTLE_TIMEFRAME = 10  # seconds

### LOG FILES ###
DJANGO_LOG_FILE = "/tmp/commcare-hq.django.log"
LOG_FILE = "/tmp/commcare-hq.log"
