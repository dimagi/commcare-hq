from __future__ import absolute_import
from __future__ import unicode_literals
import settingshelper as helper
from settings import *

# note: the only reason these are prepended to INSTALLED_APPS is because of
# a weird travis issue with kafka. if for any reason this order causes problems
# it can be reverted whenever that's figured out.
# https://github.com/dimagi/commcare-hq/pull/10034#issuecomment-174868270
INSTALLED_APPS = (
    'django_nose',
    'testapps.test_elasticsearch',
    'testapps.test_pillowtop',
) + tuple(INSTALLED_APPS)

TEST_RUNNER = 'django_nose.BasicNoseRunner'
NOSE_ARGS = [
    #'--no-migrations' # trim ~120s from test run with db tests
    #'--with-fixture-bundling',
]
NOSE_PLUGINS = [
    'corehq.tests.nose.HqTestFinderPlugin',
    'corehq.tests.noseplugins.dividedwerun.DividedWeRunPlugin',
    'corehq.tests.noseplugins.djangomigrations.DjangoMigrationsPlugin',
    'corehq.tests.noseplugins.cmdline_params.CmdLineParametersPlugin',
    'corehq.tests.noseplugins.uniformresult.UniformTestResultPlugin',

    # The following are not enabled by default
    'corehq.tests.noseplugins.logfile.LogFilePlugin',
    'corehq.tests.noseplugins.timing.TimingPlugin',
    'corehq.tests.noseplugins.output.OutputPlugin',

    # Uncomment to debug tests. Plugins have nice hooks for inspecting state
    # before/after each test or context setup/teardown, etc.
    #'corehq.tests.noseplugins.debug.DebugPlugin',
]

# these settings can be overridden with environment variables
for key, value in {
    'NOSE_DB_TEST_CONTEXT': 'corehq.tests.nose.HqdbContext',
    'NOSE_NON_DB_TEST_CONTEXT': 'corehq.tests.nose.ErrorOnDbAccessContext',

    'NOSE_IGNORE_FILES': '^localsettings',

    'NOSE_EXCLUDE_DIRS': ';'.join([
        'scripts',
    ]),
}.items():
    os.environ.setdefault(key, value)
del key, value

if "SKIP_TESTS_REQUIRING_EXTRA_SETUP" not in globals():
    SKIP_TESTS_REQUIRING_EXTRA_SETUP = False

CELERY_ALWAYS_EAGER = True
# keep a copy of the original PILLOWTOPS setting around in case other tests want it.
_PILLOWTOPS = PILLOWTOPS
PILLOWTOPS = {}

# required by auditcare tests
AUDIT_MODEL_SAVE = ['django.contrib.auth.models.User']
AUDIT_ADMIN_VIEWS = False

PHONE_TIMEZONES_HAVE_BEEN_PROCESSED = True
PHONE_TIMEZONES_SHOULD_BE_PROCESSED = True

ENABLE_PRELOGIN_SITE = True

# override dev_settings
CACHE_REPORTS = True


def _set_logging_levels(levels):
    import logging
    for path, level in levels.items():
        logging.getLogger(path).setLevel(level)
_set_logging_levels({
    # Quiet down noisy loggers. Selective removal can be handy for debugging.
    'auditcare': 'INFO',
    'boto3': 'WARNING',
    'botocore': 'INFO',
    'couchdbkit.request': 'INFO',
    'datadog': 'WARNING',
    'elasticsearch': 'ERROR',
    'quickcache': 'INFO',
    'requests.packages.urllib3': 'WARNING',
    's3transfer': 'INFO',
    'urllib3': 'WARNING',
    'kafka.conn': 'WARNING',
    'kafka.client': 'WARNING',
    'kafka.consumer.kafka': 'WARNING',
})

# use empty LOGGING dict with --debug=nose,nose.plugins to debug test discovery
# TODO empty logging config (and fix revealed deprecation warnings)
LOGGING = {
    'disable_existing_loggers': False,
    'version': 1,
    'loggers': {},
}

# Define an aaa-data database if its not already defined
# This is necessary because REPORTING_DATABASES references aaa-data.
# We must have aaa-data in a separate database
# https://github.com/dimagi/commcare-hq/pull/23351#issuecomment-467500691
if 'aaa-data' not in DATABASES:
    DATABASES['aaa-data'] = {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'aaa_commcarehq',
        'USER': 'commcarehq',
        'PASSWORD': 'commcarehq',
        'HOST': 'localhost',
        'PORT': '5432',
        'TEST': {
            'SERIALIZE': False,
        }
    }

DATABASES['icds-db'] = {
    'ENGINE': 'django.db.backends.postgresql_psycopg2',
    'DISABLE_SERVER_SIDE_CURSORS': True,
    'NAME': 'icds_db',
    'USER': 'commcarehq',
    'PASSWORD': 'commcarehq',
    'HOST': 'localhost',
    'PORT': '5432',
    'MIGRATE': False,
    'TEST': {
        'SERIALIZE': False,
    },
}

helper.assign_test_db_names(DATABASES)

REPORTING_DATABASES = {
    'default': 'default',
    'ucr': 'default',
    'icds-ucr': 'icds-db',
    'icds-ucr-non-dashboard': 'icds-db',
    'icds-test-ucr': 'icds-db',
    'aaa-data': 'aaa-data',
}

# See comment under settings.SMS_QUEUE_ENABLED
SMS_QUEUE_ENABLED = False
