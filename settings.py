# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

SECRET_KEY = 'this is not a secret key'

INSTALLED_APPS = (
    'dimagi.utils',
    'dimagi.ext',
    'couchdbkit.ext.django',
    'django.contrib.contenttypes',
    'django.contrib.auth',
)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'dimagi_utils',
    }
}



####### Couch Config ######
COUCH_DATABASE = 'http://127.0.0.1:5984/dimagi_utils'

COUCHDB_DATABASES = [(app, COUCH_DATABASE) for app in ['utils', 'ext', 'couch']]


TEST_RUNNER = 'couchdbkit.ext.django.testrunner.CouchDbKitTestSuiteRunner'

####### # Email setup ########
# Print emails to console so there is no danger of spamming, but you can still get registration URLs
EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend'
EMAIL_LOGIN = "nobody@example.com"
EMAIL_PASSWORD = "******"
EMAIL_SMTP_HOST = "smtp.example.com"
EMAIL_SMTP_PORT = 587

COVERAGE_REPORT_HTML_OUTPUT_DIR='coverage-html'
COVERAGE_MODULE_EXCLUDES= ['tests$', 'settings$', 'urls$', 'locale$',
                           'common.views.test', '^django', 'management', 'migrations',
                           '^south', '^djcelery', '^debug_toolbar', '^rosetta']

# Disable logging
LOGGING = {
    'version': 1,
    'handlers': {
        'null': {
            'level': 'DEBUG',
            'class': 'django.utils.log.NullHandler',
        },
    },
    'loggers': {
        '': {
            'level': 'CRITICAL',
            'handler': 'null',
            'propagate': False,
        }
    }
}
