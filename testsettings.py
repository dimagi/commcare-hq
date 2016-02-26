from settings import *

INSTALLED_APPS += (
    'django_nose',
)

TEST_RUNNER = 'django_nose.NoseTestSuiteRunner'
NOSE_ARGS = [
    #'--no-migrations' # trim ~120s from test run with db tests
    #'--with-fixture-bundling',
    '--logging-clear-handlers',
]
NOSE_PLUGINS = [
    'corehq.tests.nose.HqTestFinderPlugin',
    'corehq.tests.nose.OmitDjangoInitModuleTestsPlugin',
    'corehq.tests.noseplugins.djangomigrations.DjangoMigrationsPlugin',

    # The following are not enabled by default
    'corehq.tests.noseplugins.timing.TimingPlugin',
    'corehq.tests.noseplugins.uniformresult.UniformTestResultPlugin',
]

# these settings can be overridden with environment variables
for key, value in {
    'NOSE_DB_TEST_CONTEXT': 'corehq.tests.nose.HqdbContext',
    'NOSE_NON_DB_TEST_CONTEXT': 'corehq.tests.nose.ErrorOnDbAccessContext',

    'NOSE_IGNORE_FILES': '^localsettings',

    'NOSE_EXCLUDE_TESTS': ';'.join([
        'corehq.apps.ota.tests.digest_restore.DigestOtaRestoreTest'

        # revisit these (seems like they should be passing)
        'corehq.apps.ota.tests.digest_restore.DigestOtaRestoreTest', # not run by django test runner
    ]),

    'NOSE_EXCLUDE_DIRS': ';'.join([
        'scripts',
        'testapps',

        # strange error:
        # TypeError: Attribute setup of <module 'touchforms.backend' ...> is not a python function.
        'submodules/touchforms-src/touchforms/backend',
    ]),
}.items():
    os.environ.setdefault(key, value)
del key, value

# HqTestSuiteRunner settings
INSTALLED_APPS = INSTALLED_APPS + list(TEST_APPS)

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


def _clean_up_logging_output():
    import logging
    logging.getLogger('raven').setLevel('WARNING')

    # make all loggers propagate to prevent
    # "No handlers could be found for logger ..."
    # (a side effect of --logging-clear-handlers)
    for item in LOGGING["loggers"].values():
        if not item.get("propagate", True):
            item["propagate"] = True

_clean_up_logging_output()
