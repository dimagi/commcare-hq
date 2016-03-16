from settings import *

INSTALLED_APPS += (
    'django_nose',
)

TEST_RUNNER = 'django_nose.NoseTestSuiteRunner'
NOSE_ARGS = [
    #'--with-migrations' # adds ~30s to test run; TODO travis should use it
    #'--with-doctest', # adds 5s to discovery (before tests start); TODO travis should use it
    '--with-fixture-bundling',
    '--doctest-options=+NORMALIZE_WHITESPACE',
    '--logging-clear-handlers',
]
NOSE_PLUGINS = [
    # Disable migrations by default. Use --with-migrations to enable them.
    'corehq.tests.nose.DjangoMigrationsPlugin',
    'corehq.tests.nose.OmitDjangoInitModuleTestsPlugin',
    'corehq.tests.nose.HqTestFinderPlugin',

    # use with --collect-only when comparing to django runner COLLECT_ONLY output
    #'testrunner.UniformTestResultPlugin',
]

# these settings can be overridden with environment variables
for key, value in {
    'NOSE_DB_TEST_CONTEXT': 'corehq.tests.nose.HqdbContext',
    'NOSE_NON_DB_TEST_CONTEXT': 'corehq.tests.nose.ErrorOnDbAccessContext',
    'NOSE_DOCTEST_EXTENSION': '.py',

    'NOSE_IGNORE_FILES': '^(localsettings.*|setup\.py|bootstrap\.py|[0-9].*)$',

    'NOSE_EXCLUDE_TESTS': ';'.join([
        'corehq.apps.sms.tests.inbound_handlers',
        'corehq.messaging.ivrbackends.kookoo.tests.outbound',
        'corehq.apps.ota.tests.digest_restore.DigestOtaRestoreTest'
        #'pillow_retry.south_migrations',

        # revisit these (seems like they should be passing)
        'corehq.apps.ota.tests.digest_restore.DigestOtaRestoreTest', # not run by django test runner

        # ignore record_deploy_success.py because datadog may not be installed
        # (only matters when running --with-doctests)
        'corehq.apps.hqadmin.management.commands.record_deploy_success',
    ]),

    'NOSE_EXCLUDE_DIRS': ';'.join([
        'scripts',
        'testapps',

        # strange error:
        # TypeError: Attribute setup of <module 'touchforms.backend' ...> is not a python function.
        'submodules/touchforms-src/touchforms/backend',

        # excludes for --with-doctest
        # these cause gevent.threading to be imported, which causes this error:
        # DatabaseError: DatabaseWrapper objects created in a thread can only
        # be used in that same thread. ...
        'corehq/apps/hqadmin/management/commands',
        'corehq/apps/hqcase/management/commands',
        'corehq/preindex/management/commands',
        'deployment',
        'submodules/dimagi-utils-src/dimagi/utils/management/commands',
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
