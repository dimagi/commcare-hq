from __future__ import absolute_import
from __future__ import unicode_literals
import settingshelper as helper
from settings import *

USING_CITUS = any(db.get('ROLE') == 'citus_master' for db in DATABASES.values())

# note: the only reason these are prepended to INSTALLED_APPS is because of
# a weird travis issue with kafka. if for any reason this order causes problems
# it can be reverted whenever that's figured out.
# https://github.com/dimagi/commcare-hq/pull/10034#issuecomment-174868270
INSTALLED_APPS = (
    'django_nose',
    'testapps.test_elasticsearch',
    'testapps.test_pillowtop',
) + tuple(INSTALLED_APPS)

if USING_CITUS:
    if 'testapps.citus_master' not in INSTALLED_APPS:
        INSTALLED_APPS = (
            'testapps.citus_master',
            'testapps.citus_worker',
        ) + tuple(INSTALLED_APPS)

    if 'testapps.citus_master.citus_router.CitusDBRouter' not in DATABASE_ROUTERS:
        # this router must go first
        DATABASE_ROUTERS = ['testapps.citus_master.citus_router.CitusDBRouter'] + DATABASE_ROUTERS

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

CELERY_TASK_ALWAYS_EAGER = True
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
    'alembic': 'WARNING',
    'auditcare': 'INFO',
    'boto3': 'WARNING',
    'botocore': 'INFO',
    'couchdbkit.request': 'INFO',
    'couchdbkit.designer': 'WARNING',
    'datadog': 'WARNING',
    'elasticsearch': 'ERROR',
    'kafka.conn': 'WARNING',
    'kafka.client': 'WARNING',
    'kafka.consumer.kafka': 'WARNING',
    'kafka.metrics': 'WARNING',
    'kafka.protocol.parser': 'WARNING',
    'kafka.producer': 'WARNING',
    'quickcache': 'INFO',
    'requests.packages.urllib3': 'WARNING',
    's3transfer': 'INFO',
    'urllib3': 'WARNING',
})

# use empty LOGGING dict with --debug=nose,nose.plugins to debug test discovery
# TODO empty logging config (and fix revealed deprecation warnings)
LOGGING = {
    'disable_existing_loggers': False,
    'version': 1,
    'loggers': {},
}

# # Required in Python 3 to prevent transient but frequent travis errors.
# # Probably is caused by some race condition.
# if 'icds-ucr' not in DATABASES:
#     DATABASES['icds-ucr'] = {
#         'ENGINE': 'django.db.backends.postgresql_psycopg2',
#         'NAME': 'icds_commcarehq',
#         'USER': 'commcarehq',
#         'PASSWORD': 'commcarehq',
#         'HOST': 'localhost',
#         'PORT': '5432',
#         'TEST': {
#             'SERIALIZE': False,
#         }
#     }
# # Define an aaa-data database if its not already defined
# # This is necessary because REPORTING_DATABASES references aaa-data.
# # We must have aaa-data in a separate database
# # https://github.com/dimagi/commcare-hq/pull/23351#issuecomment-467500691
# if 'aaa-data' not in DATABASES:
#     DATABASES['aaa-data'] = {
#         'ENGINE': 'django.db.backends.postgresql_psycopg2',
#         'NAME': 'aaa_commcarehq',
#         'USER': 'commcarehq',
#         'PASSWORD': 'commcarehq',
#         'HOST': 'localhost',
#         'PORT': '5432',
#         'TEST': {
#             'SERIALIZE': False,
#         }
#     }
helper.assign_test_db_names(DATABASES)

REPORTING_DATABASES = {
    'default': 'default',
    'ucr': 'default',
    'icds-ucr': 'icds-ucr',
    'icds-ucr-non-dashboard': 'icds-ucr',
    'icds-test-ucr': 'icds-ucr',
    'aaa-data': 'aaa-data',
}

# See comment under settings.SMS_QUEUE_ENABLED
SMS_QUEUE_ENABLED = False
