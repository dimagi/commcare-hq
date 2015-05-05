# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

SECRET_KEY = 'this is not a secret key'

INSTALLED_APPS = (
    'couchexport',
    'couchdbkit.ext.django',
    'coverage',
    'django.contrib.contenttypes',
    'django.contrib.auth',
)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'couchexport',
    }
}

####### Couch Config ######
# required by dimagi.utils.couch.database.get_safe_write_kwargs
COUCH_SERVER_ROOT = '127.0.0.1:5984'

# NOTE: COUCH_DATABASE points to test database as a hack to make dimagi.utils.couch.database.get_db work
COUCH_DATABASE = 'http://127.0.0.1:5984/couchexport_test'


COUCHDB_DATABASES = [ (app, 'http://127.0.0.1:5984/couchexport') for app in ['couch', 'couchexport', 'ext'] ]

TEST_RUNNER = 'couchdbkit.ext.django.testrunner.CouchDbKitTestSuiteRunner'


