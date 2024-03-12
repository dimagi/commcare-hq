import os
from warnings import filterwarnings

import settingshelper as helper
from settings import *  # noqa: F403

# Commenting out temporarily for tests
# if os.environ.get('ELASTICSEARCH_MAJOR_VERSION'):
#     ELASTICSEARCH_MAJOR_VERSION = int(os.environ.get('ELASTICSEARCH_MAJOR_VERSION'))

ELASTICSEARCH_MAJOR_VERSION = 5

# timeout faster in tests
ES_SEARCH_TIMEOUT = 5

# Default multiplexed value for_test adapter
ES_FOR_TEST_INDEX_MULTIPLEXED = False
ES_FOR_TEST_INDEX_SWAPPED = False


# Set multiplexed settings to false for test runs

ES_APPS_INDEX_MULTIPLEXED = False
ES_CASE_SEARCH_INDEX_MULTIPLEXED = False
ES_CASES_INDEX_MULTIPLEXED = False
ES_DOMAINS_INDEX_MULTIPLEXED = False
ES_FORMS_INDEX_MULTIPLEXED = False
ES_GROUPS_INDEX_MULTIPLEXED = False
ES_SMS_INDEX_MULTIPLEXED = False
ES_USERS_INDEX_MULTIPLEXED = False


ES_APPS_INDEX_SWAPPED = False
ES_CASE_SEARCH_INDEX_SWAPPED = False
ES_CASES_INDEX_SWAPPED = False
ES_DOMAINS_INDEX_SWAPPED = False
ES_FORMS_INDEX_SWAPPED = False
ES_GROUPS_INDEX_SWAPPED = False
ES_SMS_INDEX_SWAPPED = False
ES_USERS_INDEX_SWAPPED = False

ES_SETTINGS = {
    'default': {
        'number_of_replicas': 0,
        'number_of_shards': 1,
    },
}

# note: the only reason these are prepended to INSTALLED_APPS is because of
# a weird travis issue with kafka. if for any reason this order causes problems
# it can be reverted whenever that's figured out.
# https://github.com/dimagi/commcare-hq/pull/10034#issuecomment-174868270
INSTALLED_APPS = (
    'django_nose',
    'testapps.test_elasticsearch',
    'testapps.test_pillowtop',
) + tuple(INSTALLED_APPS)  # noqa: F405

TEST_RUNNER = 'django_nose.BasicNoseRunner'
NOSE_ARGS = [
    #'--no-migrations' # trim ~120s from test run with db tests
    #'--with-fixture-bundling',
]
NOSE_PLUGINS = [
    'corehq.tests.nose.HqTestFinderPlugin',
    'corehq.tests.noseplugins.classcleanup.ClassCleanupPlugin',
    'corehq.tests.noseplugins.dbtransaction.DatabaseTransactionPlugin',
    'corehq.tests.noseplugins.dividedwerun.DividedWeRunPlugin',
    'corehq.tests.noseplugins.djangomigrations.DjangoMigrationsPlugin',
    'corehq.tests.noseplugins.cmdline_params.CmdLineParametersPlugin',
    'corehq.tests.noseplugins.patches.PatchesPlugin',
    'corehq.tests.noseplugins.redislocks.RedisLockTimeoutPlugin',
    'corehq.tests.noseplugins.uniformresult.UniformTestResultPlugin',

    # The following are not enabled by default
    'corehq.tests.noseplugins.logfile.LogFilePlugin',
    'corehq.tests.noseplugins.timing.TimingPlugin',
    'corehq.tests.noseplugins.output.OutputPlugin',
    'corehq.tests.noseplugins.elasticsnitch.ElasticSnitchPlugin',

    # Uncomment to debug tests. Plugins have nice hooks for inspecting state
    # before/after each test or context setup/teardown, etc.
    #'corehq.tests.noseplugins.debug.DebugPlugin',
]

# these settings can be overridden with environment variables
for key, value in {
    'NOSE_DB_TEST_CONTEXT': 'corehq.tests.nose.HqdbContext',
    'NOSE_NON_DB_TEST_CONTEXT': 'corehq.tests.nose.ErrorOnDbAccessContext',
    'NOSE_IGNORE_FILES': '^localsettings',
    'NOSE_EXCLUDE_DIRS': 'scripts',

    'DD_DOGSTATSD_DISABLE': 'true',
    'DD_TRACE_ENABLED': 'false',
}.items():
    os.environ.setdefault(key, value)
del key, value

if "SKIP_TESTS_REQUIRING_EXTRA_SETUP" not in globals():
    SKIP_TESTS_REQUIRING_EXTRA_SETUP = False

CELERY_TASK_ALWAYS_EAGER = True
# keep a copy of the original PILLOWTOPS setting around in case other tests want it.
_PILLOWTOPS = PILLOWTOPS # noqa F405
PILLOWTOPS = {}

PHONE_TIMEZONES_HAVE_BEEN_PROCESSED = True
PHONE_TIMEZONES_SHOULD_BE_PROCESSED = True

ENABLE_PRELOGIN_SITE = True

# override dev_settings
CACHE_REPORTS = True

# Hide couchdb 'unclosed socket' warnings
filterwarnings("ignore", r"unclosed.*socket.*raddr=\([^) ]* 5984\)", ResourceWarning)


def _set_logging_levels(levels):
    import logging
    for path, level in levels.items():
        logging.getLogger(path).setLevel(level)


_set_logging_levels({
    # Quiet down noisy loggers. Selective removal can be handy for debugging.
    'alembic': 'WARNING',
    'corehq.apps.auditcare': 'INFO',
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

helper.assign_test_db_names(DATABASES)  # noqa: F405
helper.update_redis_location_for_tests(CACHES)  # noqa: F405

# See comment under settings.SMS_QUEUE_ENABLED
SMS_QUEUE_ENABLED = False

# use all providers in tests
METRICS_PROVIDERS = [
    'corehq.util.metrics.datadog.DatadogMetrics',
    'corehq.util.metrics.prometheus.PrometheusMetrics',
]

FORMPLAYER_INTERNAL_AUTH_KEY = "abc123"

# A workaround to test the messaging framework. See: https://stackoverflow.com/a/60218100
MESSAGE_STORAGE = 'django.contrib.messages.storage.cookie.CookieStorage'

if os.environ.get("STRIPE_PRIVATE_KEY"):
    STRIPE_PRIVATE_KEY = os.environ.get("STRIPE_PRIVATE_KEY")
