from settings import *

INSTALLED_APPS += (
    'django_nose',
)

TEST_RUNNER = 'django_nose.NoseTestSuiteRunner'
NOSE_ARGS = [
    #'--with-migrations' # adds ~30s to test run; TODO travis should use it
    #'--with-doctest', # adds 5s to discovery (before tests start); TODO travis should use it
    '--with-fixture-bundling',
    '--logging-clear-handlers',
]
NOSE_PLUGINS = [
    # Disable migrations by default. Use --with-migrations to enable them.
    'corehq.tests.nose.DjangoMigrationsPlugin',
    'corehq.tests.nose.OmitDjangoInitModuleTestsPlugin',
]

# these settings can be overridden with environment variables
for key, value in {
    'NOSE_DB_TEST_CONTEXT': 'corehq.tests.nose.HqdbContext',
    'NOSE_NON_DB_TEST_CONTEXT': 'corehq.tests.nose.ErrorOnDbAccessContext',

    # ignore record_deploy_success.py because datadog may not be installed
    # (only matters when running --with-doctests)
    'NOSE_IGNORE_FILES': '^(localsettings|record_deploy_success\.py)',

    'NOSE_EXCLUDE_DIRS': ';'.join([
        'scripts',
        'testapps',

        # excludes for --with-doctest
        # these cause gevent.threading to be imported, which causes this error:
        # DatabaseError: DatabaseWrapper objects created in a thread can only
        # be used in that same thread. ...
        'corehq/apps/hqcase/management/commands',
        'corehq/preindex/management/commands',
        'deployment/gunicorn',
    ]),
}.items():
    os.environ.setdefault(key, value)
del key, value

# HqTestSuiteRunner settings
INSTALLED_APPS = INSTALLED_APPS + list(TEST_APPS)
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


def _set_couchdb_test_settings():
    import settingshelper

    def get_test_db_name(dbname):
        return "%s_test" % dbname

    global COUCH_DATABASE_NAME, EXTRA_COUCHDB_DATABASES

    COUCH_DATABASE_NAME = get_test_db_name(COUCH_DATABASE_NAME)
    globals().update(settingshelper.get_dynamic_db_settings(
        COUCH_SERVER_ROOT,
        COUCH_USERNAME,
        COUCH_PASSWORD,
        COUCH_DATABASE_NAME,
    ))

    EXTRA_COUCHDB_DATABASES = {
        db_name: get_test_db_name(url)
        for db_name, url in EXTRA_COUCHDB_DATABASES.items()
    }

_set_couchdb_test_settings()


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
