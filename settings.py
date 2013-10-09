#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8
from collections import defaultdict

import sys, os
from django.contrib import messages

# odd celery fix
import djcelery;

djcelery.setup_loader()

CACHE_BACKEND = 'memcached://127.0.0.1:11211/'

DEBUG = True
TEMPLATE_DEBUG = DEBUG

try:
    UNIT_TESTING = 'test' == sys.argv[1]
except IndexError:
    UNIT_TESTING = False

ADMINS = ()
MANAGERS = ADMINS

# Ensure that extraneous Tastypie formats are not actually used
# Curiously enough, browsers prefer html, then xml, lastly (or not at all) json
# so removing html from the this variable annoyingly makes it render as XML
# in the browser, when we want JSON. So I've added this commented
# to document intent, but it should only really be activated
# when we have logic in place to treat direct browser access specially.
#TASTYPIE_DEFAULT_FORMATS=['json', 'xml', 'yaml']

# default to the system's timezone settings
TIME_ZONE = "UTC"


# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

LANGUAGES = (
    ('en', 'English'),
    ('fr', 'French'),
    ('hin', 'Hindi'),
)

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = '/media/'
STATIC_URL = '/static/'

FILEPATH = os.path.abspath(os.path.dirname(__file__))
# media for user uploaded media.  in general this won't be used at all.
MEDIA_ROOT = os.path.join(FILEPATH, 'mediafiles')
STATIC_ROOT = os.path.join(FILEPATH, 'staticfiles')


# Django i18n searches for translation files (django.po) within this dir
# and then in the locale/ directories of installed apps
LOCALE_PATHS = (
    os.path.join(FILEPATH, 'locale'),
)

STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder"
)

STATICFILES_DIRS = (
    ('formdesigner', os.path.join(FILEPATH, 'submodules', 'formdesigner')),
)

DJANGO_LOG_FILE = "%s/%s" % (FILEPATH, "commcarehq.django.log")

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/static/admin/'

# Make this unique, and don't share it with anybody - put into localsettings.py
SECRET_KEY = ''

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
    'django.template.loaders.eggs.Loader',
    #     'django.template.loaders.eggs.load_template_source',
)

MIDDLEWARE_CLASSES = [
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'corehq.middleware.OpenRosaMiddleware',
    'corehq.apps.users.middleware.UsersMiddleware',
    'casexml.apps.phone.middleware.SyncTokenMiddleware',
    'auditcare.middleware.AuditMiddleware',
    'no_exceptions.middleware.NoExceptionsMiddleware',
]

ROOT_URLCONF = "urls"

TEMPLATE_CONTEXT_PROCESSORS = [
    "django.contrib.auth.context_processors.auth",
    "django.core.context_processors.debug",
    "django.core.context_processors.i18n",
    "django.core.context_processors.media",
    "django.core.context_processors.request",
    "django.contrib.messages.context_processors.messages",
    'django.core.context_processors.static',
    "corehq.util.context_processors.current_url_name",
    'corehq.util.context_processors.domain',
    "corehq.util.context_processors.base_template", # sticks the base template inside all responses
    "corehq.util.context_processors.analytics_js",
    "corehq.util.context_processors.raven",
]

TEMPLATE_DIRS = [
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
]

DEFAULT_APPS = (
    'corehq.apps.userhack', # this has to be above auth
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    #'django.contrib.messages', # don't need this for messages and it's causing some error
    'django.contrib.staticfiles',
    'south',
    'djcelery', # pip install django-celery
    'djtables', # pip install djtables
    #'ghettoq',     # pip install ghettoq
    'djkombu', # pip install django-kombu
    'couchdbkit.ext.django',
    'crispy_forms',
    'django.contrib.markup',
    'gunicorn',
    'raven.contrib.django.raven_compat',
    # 'weasyprint',
)

CRISPY_TEMPLATE_PACK = 'bootstrap'

HQ_APPS = (
    'django_digest',
    'rosetta',
    'auditcare',
    'djangocouch',
    'djangocouchuser',
    'hqscripts',
    'casexml.apps.case',
    'casexml.apps.phone',
    'corehq.apps.cleanup',
    'corehq.apps.cloudcare',
    'corehq.apps.appstore',
    'corehq.apps.domain',
    'corehq.apps.domainsync',
    'corehq.apps.hqadmin',
    'corehq.apps.hqcase',
    'corehq.apps.hqcouchlog',
    'corehq.apps.hqwebapp',
    'corehq.apps.hqmedia',
    'corehq.apps.locations',
    'corehq.apps.commtrack',
    'couchforms',
    'couchexport',
    'couchlog',
    'ctable',
    'ctable_view',
    'dimagi.utils',
    'formtranslate',
    'receiver',
    'langcodes',
    'corehq.apps.adm',
    'corehq.apps.announcements',
    'corehq.apps.callcenter',
    'corehq.apps.crud',
    'corehq.apps.receiverwrapper',
    'corehq.apps.migration',
    'corehq.apps.app_manager',
    'corehq.apps.facilities',
    'corehq.apps.fixtures',
    'corehq.apps.importer',
    'corehq.apps.reminders',
    'corehq.apps.prescriptions',
    'corehq.apps.reportfixtures',
    'corehq.apps.translations',
    'corehq.apps.users',
    'corehq.apps.settings',
    'corehq.apps.ota',
    'corehq.apps.groups',
    'corehq.apps.mobile_auth',
    'corehq.apps.sms',
    'corehq.apps.smsforms',
    'corehq.apps.ivr',
    'corehq.apps.tropo',
    'corehq.apps.kookoo',
    'corehq.apps.sislog',
    'corehq.apps.yo',
    'corehq.apps.telerivet',
    'corehq.apps.mach',
    'corehq.apps.registration',
    'corehq.apps.unicel',
    'corehq.apps.reports',
    'corehq.apps.data_interfaces',
    'corehq.apps.export',
    'corehq.apps.builds',
    'corehq.apps.orgs',
    'corehq.apps.api',
    'corehq.apps.indicators',
    'corehq.couchapps',
    'custom.apps.wisepill',
    'fluff',
    'fluff.fluff_filter',
    'soil',
    'touchforms.formplayer',
    'hqbilling',
    'phonelog',
    'hutch',
    'pillowtop',
    'hqstyle',

    # custom reports
    'a5288',
    'custom.bihar',
    'dca',
    'custom.apps.gsid',
    'hsph',
    'mvp',
    'mvp_apps',
    'custom.opm.opm_reports',
    'custom.opm.opm_tasks',
    'pathfinder',
    'pathindia',
    'pact',
    'psi',

    'custom.apps.care_benin',
    'custom.reports.care_sa',
    'custom.apps.cvsu',
    'custom.reports.mc',
    'custom.trialconnect',
    'custom.apps.crs_reports',
    'custom.hope',
)

TEST_APPS = ()

# also excludes any app starting with 'django.'
APPS_TO_EXCLUDE_FROM_TESTS = (
    'a5288',
    'couchdbkit.ext.django',
    'corehq.apps.data_interfaces',
    'corehq.apps.ivr',
    'corehq.apps.kookoo',
    'corehq.apps.mach',
    'corehq.apps.ota',
    'corehq.apps.settings',
    'corehq.apps.sislog',
    'corehq.apps.telerivet',
    'corehq.apps.tropo',
    'corehq.apps.yo',
    'crispy_forms',
    'django_extensions',
    'djcelery',
    'djtables',
    'djkombu',
    'gunicorn',
    'langcodes',
    'luna',
    'raven.contrib.django.raven_compat',
    'rosetta',
    'soil',
    'south',
    # 'weasyprint',
    'custom.apps.crs_reports',

    # submodules with tests that run on travis
    'casexml.apps.case',
    'casexml.apps.phone',
    'couchforms',
    'ctable',
    'ctable_view',
    'dimagi.utils',
    'fluff',
    'fluff_filter',
    'freddy',
    'pillowtop',
    'receiver',
)

INSTALLED_APPS = DEFAULT_APPS + HQ_APPS


# after login, django redirects to this URL
# rather than the default 'accounts/profile'
LOGIN_REDIRECT_URL = '/'


# Default reporting database should be overridden in localsettings.
SQL_REPORTING_DATABASE_URL = "sqlite:////tmp/commcare_reporting_test.db"

REPORT_CACHE = 'default' # or e.g. 'redis'

####### Domain settings  #######

DOMAIN_MAX_REGISTRATION_REQUESTS_PER_DAY = 99
DOMAIN_SELECT_URL = "/domain/select/"

# This is not used by anything in CommCare HQ, leaving it here in case anything
# in Django unexpectedly breaks without it.  When you need the login url, you
# should use reverse('login', kwargs={'domain_type': domain_type}) in order to
# maintain CommCare HQ/CommTrack distinction.
LOGIN_URL = "/accounts/login/"
# If a user tries to access domain admin pages but isn't a domain
# administrator, here's where he/she is redirected
DOMAIN_NOT_ADMIN_REDIRECT_PAGE_NAME = "homepage"

# domain syncs
# e.g.
#               { sourcedomain1: { "domain": targetdomain1,
#                      "transform": path.to.transformfunction1 },
#                 sourcedomain2: {...} }
DOMAIN_SYNCS = {}
# if you want to deidentify app names, put a dictionary in your settings
# of source names to deidentified names
DOMAIN_SYNC_APP_NAME_MAP = {}
DOMAIN_SYNC_DATABASE_NAME = "commcarehq-public"


####### Release Manager App settings  #######
RELEASE_FILE_PATH = os.path.join("data", "builds")

## soil heartbead config ##
SOIL_HEARTBEAT_CACHE_KEY = "django-soil-heartbeat"


####### Shared/Global/UI Settings ######

# restyle some templates
BASE_TEMPLATE = "hqwebapp/base.html"
LOGIN_TEMPLATE = "login_and_password/login.html"
LOGGEDOUT_TEMPLATE = "loggedout.html"

# email settings: these ones are the custom hq ones
EMAIL_LOGIN = "user@domain.com"
EMAIL_PASSWORD = "changeme"
EMAIL_SMTP_HOST = "smtp.gmail.com"
EMAIL_SMTP_PORT = 587

# put email addresses here to have them receive bug reports
BUG_REPORT_RECIPIENTS = ()
EXCHANGE_NOTIFICATION_RECIPIENTS = []

SERVER_EMAIL = 'commcarehq-noreply@dimagi.com' #the physical server emailing - differentiate if needed
DEFAULT_FROM_EMAIL = 'commcarehq-noreply@dimagi.com'
SUPPORT_EMAIL = "commcarehq-support@dimagi.com"
CCHQ_BUG_REPORT_EMAIL = 'commcarehq-bug-reports@dimagi.com'
EMAIL_SUBJECT_PREFIX = '[commcarehq] '

SERVER_ENVIRONMENT = 'localdev'

PAGINATOR_OBJECTS_PER_PAGE = 15
PAGINATOR_MAX_PAGE_LINKS = 5

# OpenRosa Standards
OPENROSA_VERSION = "1.0"

# OTA restore fixture generators
FIXTURE_GENERATORS = [
    "corehq.apps.users.fixturegenerators.user_groups",
    "corehq.apps.fixtures.fixturegenerators.item_lists",
    "corehq.apps.reportfixtures.fixturegenerators.indicators",
    "custom.bihar.reports.indicators.fixtures.generator",
]

GET_URL_BASE = 'dimagi.utils.web.get_url_base'

SMS_GATEWAY_URL = "http://localhost:8001/"
SMS_GATEWAY_PARAMS = "user=my_username&password=my_password&id=%(phone_number)s&text=%(message)s"

# celery
BROKER_URL = 'django://' #default django db based

#this is the default celery queue - for periodic tasks on a separate queue override this to something else
CELERY_PERIODIC_QUEUE = 'celery'

from celery.schedules import crontab
# schedule options can be seen here:
# http://docs.celeryproject.org/en/latest/reference/celery.schedules.html
CELERYBEAT_SCHEDULE = {
    'monthly-opm-report-snapshot': {
        'task': 'custom.opm.opm_tasks.tasks.snapshot',
        'schedule': crontab(hour=1, day_of_month=1),
    },
}

SKIP_SOUTH_TESTS = True
#AUTH_PROFILE_MODULE = 'users.HqUserProfile'
TEST_RUNNER = 'testrunner.HqTestSuiteRunner'
HQ_ACCOUNT_ROOT = "commcarehq.org" # this is what gets appended to @domain after your accounts

XFORMS_PLAYER_URL = "http://localhost:4444/"  # touchform's setting

####### Couchlog config ######

COUCHLOG_BLUEPRINT_HOME = "%s%s" % (STATIC_URL, "hqwebapp/stylesheets/blueprint/")
COUCHLOG_DATATABLES_LOC = "%s%s" % (
    STATIC_URL, "hqwebapp/js/lib/datatables-1.9/js/jquery.dataTables.min.js")

COUCHLOG_JQMODAL_LOC = "%s%s" % (STATIC_URL, "hqwebapp/js/lib/jqModal.js")
COUCHLOG_JQMODAL_CSS_LOC = "%s%s" % (STATIC_URL, "hqwebapp/stylesheets/jqModal.css")

# These allow HQ to override what shows up in couchlog (add a domain column)
COUCHLOG_TABLE_CONFIG = {"id_column": 0,
                         "archived_column": 1,
                         "date_column": 2,
                         "message_column": 4,
                         "actions_column": 8,
                         "email_column": 9,
                         "no_cols": 10}
COUCHLOG_DISPLAY_COLS = ["id", "archived?", "date", "exception type",
                         "message", "domain", "user", "url", "actions", "report"]
COUCHLOG_RECORD_WRAPPER = "corehq.apps.hqcouchlog.wrapper"
COUCHLOG_DATABASE_NAME = "commcarehq-couchlog"

# couchlog/case search
LUCENE_ENABLED = False



# unicel sms config
UNICEL_CONFIG = {"username": "Dimagi",
                 "password": "changeme",
                 "sender": "Promo"}

# mach sms config
MACH_CONFIG = {"username": "Dimagi",
               "password": "changeme",
               "service_profile": "changeme"}

#auditcare parameters
AUDIT_MODEL_SAVE = [
    'corehq.apps.app_manager.Application',
    'corehq.apps.app_manager.RemoteApp',
]
AUDIT_VIEWS = [
    'corehq.apps.domain.views.registration_request',
    'corehq.apps.domain.views.registration_confirm',
    'corehq.apps.domain.views.password_change',
    'corehq.apps.domain.views.password_change_done',
    'corehq.apps.reports.views.submit_history',
    'corehq.apps.reports.views.active_cases',
    'corehq.apps.reports.views.submit_history',
    'corehq.apps.reports.views.default',
    'corehq.apps.reports.views.submission_log',
    'corehq.apps.reports.views.form_data',
    'corehq.apps.reports.views.export_data',
    'corehq.apps.reports.views.excel_report_data',
    'corehq.apps.reports.views.daily_submissions',
]

# Don't use google analytics unless overridden in localsettings
ANALYTICS_IDS = {
    'GOOGLE_ANALYTICS_ID': '',
    'PINGDOM_ID': ''
}

# for touchforms maps
GMAPS_API_KEY = "changeme"

# for touchforms authentication
TOUCHFORMS_API_USER = "changeme"
TOUCHFORMS_API_PASSWORD = "changeme"

# import local settings if we find them
LOCAL_APPS = ()
LOCAL_COUCHDB_APPS = ()
LOCAL_MIDDLEWARE_CLASSES = ()
LOCAL_PILLOWTOPS = []

#If there are existing doc_ids and case_ids you want to check directly - they are refernced
#in your localsettings for more accurate direct checks, otherwise use view based which can be inaccurate.
ES_CASE_CHECK_DIRECT_DOC_ID = None
ES_XFORM_CHECK_DIRECT_DOC_ID = None

# our production logstash aggregation
LOGSTASH_DEVICELOG_PORT = 10777
LOGSTASH_COUCHLOG_PORT = 10888
LOGSTASH_AUDITCARE_PORT = 10999
LOGSTASH_HOST = 'localhost'

#on both a single instance or distributed setup this should assume to be localhost
ELASTICSEARCH_HOST = 'localhost'
ELASTICSEARCH_PORT = 9200

####### Couch Config ######
#for production this ought to be set to true on your configured couch instance
COUCH_HTTPS = False
COUCH_SERVER_ROOT = 'localhost:5984'  # 6984 for https couch
COUCH_USERNAME = ''
COUCH_PASSWORD = ''
COUCH_DATABASE_NAME = 'commcarehq'

BITLY_LOGIN = ''
BITLY_APIKEY = ''

# this should be overridden in localsettings
INTERNAL_DATA = defaultdict(list)

COUCH_STALE_QUERY='update_after'  # 'ok' for cloudant


MESSAGE_LOG_OPTIONS = {
    "abbreviated_phone_number_domains": ["mustmgh", "mgh-cgh-uganda"],
}

IVR_OUTBOUND_RETRIES = 3
IVR_OUTBOUND_RETRY_INTERVAL = 10

# List of Fluff pillow classes that ctable should process diffs for
FLUFF_PILLOW_TYPES_TO_SQL = {
    'UnicefMalawiFluff': 'SQL',
    'MalariaConsortiumFluff': 'SQL',
    'CareSAFluff': 'SQL',
}

try:
    #try to see if there's an environmental variable set for local_settings
    if os.environ.get('CUSTOMSETTINGS', None) == "demo":
        # this sucks, but is a workaround for supporting different settings
        # in the same environment
        from settings_demo import *
    else:
        from localsettings import *
except ImportError:
    pass

LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
        },
        'simple': {
            'format': '%(asctime)s %(levelname)s %(message)s'
        },

        'pillowtop': {
            'format': '%(asctime)s %(levelname)s %(module)s %(message)s'
        },
    },
    'handlers': {
        'pillowtop': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'pillowtop'
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'formatter': 'verbose',
            'filename': DJANGO_LOG_FILE
        },
        'couchlog': {
            'level': 'WARNING',
            'class': 'couchlog.handlers.CouchHandler',
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
        },
        'sentry': {
            'level': 'ERROR',
            'class': 'raven.contrib.django.raven_compat.handlers.SentryHandler',
        },
    },
    'loggers': {
        '': {
            'handlers': ['console', 'file', 'couchlog', 'sentry'],
            'propagate': True,
            'level': 'INFO',
        },
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
        'notify': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
        'celery.task': {
            'handlers': ['console', 'file', 'couchlog'],
            'level': 'INFO',
            'propagate': True
        },
        'pillowtop': {
            'handlers': ['pillowtop'],
            'level': 'ERROR',
            'propagate': False,
        }
    }
}

if DEBUG:
    try:
        import luna
        del luna
    except ImportError:
        pass
    else:
        INSTALLED_APPS = INSTALLED_APPS + (
            'luna',
        )

    import warnings
    warnings.simplefilter('default')

if not DEBUG:
    TEMPLATE_LOADERS = [
        ('django.template.loaders.cached.Loader', TEMPLATE_LOADERS),
    ]

####### South Settings #######
#SKIP_SOUTH_TESTS=True
#SOUTH_TESTS_MIGRATE=False

####### Couch Forms & Couch DB Kit Settings #######
from settingshelper import get_dynamic_db_settings, make_couchdb_tuple

_dynamic_db_settings = get_dynamic_db_settings(COUCH_SERVER_ROOT, COUCH_USERNAME, COUCH_PASSWORD,
                                               COUCH_DATABASE_NAME, INSTALLED_APPS,
                                               use_https=COUCH_HTTPS)

# create local server and database configs
COUCH_SERVER = _dynamic_db_settings["COUCH_SERVER"]
COUCH_DATABASE = _dynamic_db_settings["COUCH_DATABASE"]

# other urls that depend on the server
XFORMS_POST_URL = _dynamic_db_settings["XFORMS_POST_URL"]

COUCHDB_APPS = [
    'adm',
    'announcements',
    'api',
    'app_manager',
    'appstore',
    'orgs',
    'auditcare',
    'builds',
    'case',
    'callcenter',
    'cleanup',
    'cloudcare',
    'commtrack',
    'couch',
    # This is necessary for abstract classes in dimagi.utils.couch.undo; otherwise breaks tests
    'couchdbkit_aggregate',
    'couchforms',
    'couchexport',
    'ctable',
    'hqadmin',
    'domain',
    'facilities',
    'fluff_filter',
    'fixtures',
    'groups',
    'hqcase',
    'hqmedia',
    'hope',
    'importer',
    'indicators',
    'locations',
    'migration',
    'mobile_auth',
    'phone',
    'reminders',
    'reportfixtures',
    'prescriptions',
    'reports',
    'sms',
    'smsforms',
    'telerivet',
    'translations',
    'users',
    'utils',  # dimagi-utils
    'formplayer',
    'phonelog',
    'registration',
    'hutch',
    'hqbilling',
    'couchlog',
    'wisepill',
    'crs_reports',

    # custom reports
    'care_benin',
    'dca',
    'gsid',
    'hsph',
    'mvp',
    'opm_tasks',
    'pathfinder',
    'pathindia',
    'pact',
    'psi',
    'trialconnect',
]

COUCHDB_APPS += LOCAL_COUCHDB_APPS

COUCHDB_DATABASES = [make_couchdb_tuple(app_label, COUCH_DATABASE) for app_label in COUCHDB_APPS]

COUCHDB_DATABASES += [
    ('fluff', COUCH_DATABASE + '__fluff-bihar'),  # needed to make couchdbkit happy
    ('bihar', COUCH_DATABASE + '__fluff-bihar'),
    ('opm_reports', COUCH_DATABASE + '__fluff-opm'),
    ('fluff', COUCH_DATABASE + '__fluff-opm'),
    ('care_sa', COUCH_DATABASE + '__fluff-care_sa'),
    ('cvsu', COUCH_DATABASE + '__fluff-cvsu'),
    ('mc', COUCH_DATABASE + '__fluff-mc'),
    ('receiverwrapper', COUCH_DATABASE + '__receiverwrapper'),
]

INSTALLED_APPS += LOCAL_APPS

MIDDLEWARE_CLASSES += LOCAL_MIDDLEWARE_CLASSES

# these are the official django settings
# which really we should be using over the custom ones
EMAIL_HOST = EMAIL_SMTP_HOST
EMAIL_PORT = EMAIL_SMTP_PORT
EMAIL_HOST_USER = EMAIL_LOGIN
EMAIL_HOST_PASSWORD = EMAIL_PASSWORD
EMAIL_USE_TLS = True
SEND_BROKEN_LINK_EMAILS = True

NO_HTML_EMAIL_MESSAGE = """
This is an email from CommCare HQ. You're seeing this message because your
email client chose to display the plaintext version of an email that CommCare
HQ can only provide in HTML.  Please set your email client to view this email
in HTML or read this email in a client that supports HTML email.

Thanks,
The CommCare HQ Team"""


MESSAGE_TAGS = {
    messages.INFO: 'alert-info',
    messages.DEBUG: '',
    messages.SUCCESS: 'alert-success',
    messages.WARNING: 'alert-error',
    messages.ERROR: 'alert-error',
}

COMMCARE_USER_TERM = "Mobile Worker"
WEB_USER_TERM = "Web User"

DEFAULT_CURRENCY = "USD"

SMS_HANDLERS = [
    'corehq.apps.sms.api.forwarding_handler',
    'corehq.apps.commtrack.sms.handle',
    'corehq.apps.sms.api.structured_sms_handler',
    'corehq.apps.sms.api.form_session_handler',
    'corehq.apps.sms.api.fallback_handler',
]

SMS_LOADED_BACKENDS = [
    "corehq.apps.unicel.api.UnicelBackend",
    "corehq.apps.mach.api.MachBackend",
    "corehq.apps.tropo.api.TropoBackend",
    "corehq.apps.sms.backend.http_api.HttpBackend",
    "corehq.apps.telerivet.models.TelerivetBackend",
    "corehq.apps.sms.test_backend.TestSMSBackend",
    "corehq.apps.sms.backend.test.TestBackend",
]

SELENIUM_APP_SETTING_DEFAULTS = {
    'cloudcare': {
        # over-generous defaults for now
        'OPEN_FORM_WAIT_TIME': 20,
        'SUBMIT_FORM_WAIT_TIME': 20
    },

    'reports': {
        'MAX_PRELOAD_TIME': 20,
        'MAX_LOAD_TIME': 30,
    },
}

INDICATOR_CONFIG = {
    "mvp-sauri": ['mvp_indicators'],
    "mvp-potou": ['mvp_indicators'],
}

CASE_WRAPPER = 'corehq.apps.hqcase.utils.get_case_wrapper'

PILLOWTOPS = [
                 'corehq.pillows.case.CasePillow',
                 'corehq.pillows.fullcase.FullCasePillow',
                 'corehq.pillows.xform.XFormPillow',
                 'corehq.pillows.fullxform.FullXFormPillow',
                 'corehq.pillows.domain.DomainPillow',
                 'corehq.pillows.user.UserPillow',
                 'corehq.pillows.application.AppPillow',
                 'corehq.pillows.sms.SMSPillow',
                 'corehq.pillows.commtrack.ConsumptionRatePillow',
                 'corehq.pillows.reportxform.ReportXFormPillow',
                 'corehq.pillows.reportcase.ReportCasePillow',
                 # fluff
                 'custom.bihar.models.CareBiharFluffPillow',
                 'custom.opm.opm_reports.models.OpmCaseFluffPillow',
                 'custom.opm.opm_reports.models.OpmUserFluffPillow',
                 'custom.opm.opm_reports.models.OpmFormFluffPillow',
                 'custom.apps.cvsu.models.UnicefMalawiFluffPillow',
                 'custom.reports.care_sa.models.CareSAFluffPillow',
                 'custom.reports.mc.models.MalariaConsortiumFluffPillow',
                 # MVP
                 'corehq.apps.indicators.pillows.FormIndicatorPillow',
                 'corehq.apps.indicators.pillows.CaseIndicatorPillow',
                 # TrialConnect
                 'custom.trialconnect.smspillow.TCSMSPillow',
             ] + LOCAL_PILLOWTOPS

#Custom workflow for indexing xform data beyond the standard properties
XFORM_PILLOW_HANDLERS = ['pact.pillowhandler.PactHandler', ]

#Custom fully indexed domains for FullCase index/pillowtop
# Adding a domain will not automatically index that domain's existing cases
ES_CASE_FULL_INDEX_DOMAINS = [
    'pact',
    'hsph',
    'care-bihar',
    'hsph-dev',
    'hsph-betterbirth-pilot-2',
    'commtrack-public-demo',
    'uth-rhd-test',
    'crs-remind',
]

#Custom fully indexed domains for FullXForm index/pillowtop --
# only those domains that don't require custom pre-processing before indexing,
# otherwise list in XFORM_PILLOW_HANDLERS
# Adding a domain will not automatically index that domain's existing forms
ES_XFORM_FULL_INDEX_DOMAINS = [
    'commtrack-public-demo',
    'uth-rhd-test',
    'mvp-bonsaaso',
    'mvp-koraro',
    'mvp-mbola',
    'mvp-mwandama',
    'mvp-potou',
    'mvp-ruhiira',
    'mvp-sada',
    'mvp-sauri',
    'mvp-tiby',
]

REMOTE_APP_NAMESPACE = "%(domain)s.commcarehq.org"

# mapping of domains to modules for those that aren't identical
# a DOMAIN_MODULE_CONFIG doc present in your couchdb can override individual
# items.
DOMAIN_MODULE_MAP = {
    'a5288-test': 'a5288',
    'a5288-study': 'a5288',
    'care-bihar': 'custom.bihar',
    'care-ihapc-live': 'custom.reports.care_sa',
    'cvsulive': 'custom.apps.cvsu',
    'dca-malawi': 'dca',
    'eagles-fahu': 'dca',
    'gsid': 'custom.apps.gsid',
    'gsid-demo': 'custom.apps.gsid',
    'hsph-dev': 'hsph',
    'hsph-betterbirth-pilot-2': 'hsph',
    'mc-inscale': 'custom.reports.mc',
    'mvp-potou': 'mvp',
    'mvp-sauri': 'mvp',
    'mvp-bonsaaso': 'mvp',
    'mvp-ruhiira': 'mvp',
    'mvp-mwandama': 'mvp',
    'mvp-sada': 'mvp',
    'opm': 'custom.opm.opm_reports',
    'psi-unicef': 'psi',
    'project': 'custom.apps.care_benin',

    'gc': 'custom.trialconnect',
    'tc-test': 'custom.trialconnect',
    'trialconnect': 'custom.trialconnect',

    'crs-remind': 'custom.apps.crs_reports'
}

CASEXML_FORCE_DOMAIN_CHECK = True
