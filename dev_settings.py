"""
This is a home for shared dev settings.  Feel free to add anything that all
devs should have set.

Add `from dev_settings import *` to the top of your localsettings file to use.
You can then override or append to any of these settings there.
"""
from __future__ import absolute_import
from __future__ import unicode_literals
import os

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
    ('corehq.apps.app_manager.models', b'Application'),
    ('corehq.apps.domain.models', b'Domain'),
    ('corehq.apps.groups.models', b'Group'),
    ('corehq.apps.users.models', (b'CouchUser', b'WebUser', b'CommCareUser')),
    ('casexml.apps.case.models', b'CommCareCase'),
    ('corehq.form_processor.interfaces.dbaccessors', (b'CaseAccessors', b'FormAccessors')),
    ('couchforms.models', b'XFormInstance'),

    # Data querying utils
    ('dimagi.utils.couch.database', b'get_db'),
    ('corehq.apps', b'es'),
)

INTERNAL_IPS = ['127.0.0.1']
ALLOWED_HOSTS = ['*']
FIX_LOGGER_ERROR_OBFUSCATION = True
LOCAL_LOGGING_LOGGERS = {
    'auditcare': {
        'handlers': ['null'],
        'level': 'WARNING',
    },
    'raven': {
        'handlers': ['null'],
        'level': 'WARNING',
    }
}

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'commcarehq',
        'USER': 'commcarehq',
        'PASSWORD': 'commcarehq',
        'HOST': 'localhost',
        'PORT': '5432'
    }
}

COUCH_DATABASES = {
    'default': {
        'COUCH_HTTPS': False,
        'COUCH_SERVER_ROOT': 'localhost:5984',
        'COUCH_USERNAME': 'commcarehq',
        'COUCH_PASSWORD': 'commcarehq',
        'COUCH_DATABASE_NAME': 'commcarehq'
    },
}

CACHES = {'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}}

# Use faster compressor that doesn't do source maps
COMPRESS_JS_COMPRESSOR = 'compressor.js.JsCompressor'

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

FORMPLAYER_INTERNAL_AUTH_KEY = "secretkey"

# use console email by default
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
