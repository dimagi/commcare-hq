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
COUCH_HTTPS = False # recommended production value is True if enabling https
COUCH_SERVER_ROOT = '127.0.0.1:5984' #6984 for https couch
COUCH_USERNAME = ''
COUCH_PASSWORD = ''
COUCH_DATABASE_NAME = 'couchexport'

COUCH_DATABASE = 'http://127.0.0.1:5984/couchlog_test'

COUCHDB_DATABASES = [ (app, 'http://127.0.0.1:5984/couchexport') for app in ['couch', 'couchexport'] ]

TEST_RUNNER = 'couchdbkit.ext.django.testrunner.CouchDbKitTestSuiteRunner'


