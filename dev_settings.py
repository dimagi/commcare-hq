"""
This is a home for shared dev settings.  Feel free to add anything that all
devs should have set.

Add `from dev_settings import *` to the top of your localsettings file to use.
You can then override or append to any of these settings there.
"""
import os

LOCAL_APPS = (
    'django_extensions',
    # for tests
    'testapps.test_elasticsearch',
    'testapps.test_pillowtop',
)

TEST_RUNNER = 'testrunner.DevTestRunner'

SKIP_TESTS_REQUIRING_EXTRA_SETUP = True

# https://docs.djangoproject.com/en/1.8/ref/settings/#std:setting-TEST_NON_SERIALIZED_APPS
# https://docs.djangoproject.com/en/1.8/ref/settings/#serialize
TEST_NON_SERIALIZED_APPS = ['corehq.form_processor']

####### Django Extensions #######
# These things will be imported when you run ./manage.py shell_plus
SHELL_PLUS_POST_IMPORTS = (
    # Models
    ('corehq.apps.domain.models', 'Domain'),
    ('corehq.apps.groups.models', 'Group'),
    ('corehq.apps.locations.models', 'Location'),
    ('corehq.apps.users.models', ('CouchUser', 'WebUser', 'CommCareUser')),
    ('casexml.apps.case.models', 'CommCareCase'),
    ('couchforms.models', 'XFormInstance'),

    # Data querying utils
    ('dimagi.utils.couch.database', 'get_db'),
    ('corehq.apps.sofabed.models', ('FormData', 'CaseData')),
    ('corehq.apps.es', '*'),
)

ALLOWED_HOSTS = ['*']
FIX_LOGGER_ERROR_OBFUSCATION = True

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

CACHES = {'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}}

# Use faster compressor that doesn't do source maps
COMPRESS_JS_COMPRESSOR = 'compressor.js.JsCompressor'

PILLOWTOP_MACHINE_ID = 'testhq'  # for tests

#  make celery synchronous
CELERY_ALWAYS_EAGER = True
# Fail hard in tasks so you get a traceback
CELERY_EAGER_PROPAGATES_EXCEPTIONS = True

# default inactivity timeout to 1 year
INACTIVITY_TIMEOUT = 60 * 24 * 365

CACHE_REPORTS = False

# Fail hard on csrf failures during dev
CSRF_SOFT_MODE = False

# Make a dir to use for storing attachments as blobs on the filesystem
shared_dirname = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                              'sharedfiles')
if not os.path.exists(shared_dirname):
    os.mkdir(shared_dirname)
SHARED_DRIVE_ROOT = shared_dirname
