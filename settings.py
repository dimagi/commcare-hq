#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8
from collections import defaultdict

import sys
import os
from urllib import urlencode
from django.contrib import messages

# odd celery fix
import djcelery

djcelery.setup_loader()

CACHE_BACKEND = 'memcached://127.0.0.1:11211/'

DEBUG = True
TEMPLATE_DEBUG = DEBUG
LESS_DEBUG = DEBUG

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
    ('fra', 'French'),  # we need this alias
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
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    'compressor.finders.CompressorFinder',
)

STATICFILES_DIRS = (
    ('formdesigner', os.path.join(FILEPATH, 'submodules', 'formdesigner')),
)

DJANGO_LOG_FILE = "%s/%s" % (FILEPATH, "commcarehq.django.log")
ACCOUNTING_LOG_FILE = "%s/%s" % (FILEPATH, "commcarehq.accounting.log")

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/static/admin/'

# Make this unique, and don't share it with anybody - put into localsettings.py
SECRET_KEY = 'you should really change this'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
    'django.template.loaders.eggs.Loader',
)

MIDDLEWARE_CLASSES = [
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'corehq.middleware.OpenRosaMiddleware',
    'corehq.apps.users.middleware.UsersMiddleware',
    'corehq.apps.domain.middleware.CCHQPRBACMiddleware',
    'casexml.apps.phone.middleware.SyncTokenMiddleware',
    'auditcare.middleware.AuditMiddleware',
    'no_exceptions.middleware.NoExceptionsMiddleware',
]

SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

PASSWORD_HASHERS = (
    # this is the default list with SHA1 moved to the front
    'django.contrib.auth.hashers.SHA1PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptPasswordHasher',
    'django.contrib.auth.hashers.MD5PasswordHasher',
    'django.contrib.auth.hashers.UnsaltedMD5PasswordHasher',
    'django.contrib.auth.hashers.CryptPasswordHasher',
)

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
    # sticks the base template inside all responses
    "corehq.util.context_processors.base_template",
    "corehq.util.context_processors.analytics_js",
    "corehq.util.context_processors.raven",
]

TEMPLATE_DIRS = []

DEFAULT_APPS = (
    'corehq.apps.userhack',  # this has to be above auth
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.humanize',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'south',
    'djcelery',
    'djtables',
    'django_prbac',
    'djkombu',
    'couchdbkit.ext.django',
    'crispy_forms',
    'django.contrib.markup',
    'gunicorn',
    'raven.contrib.django.raven_compat',
    'compressor',
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
    'casexml.apps.stock',
    'corehq.apps.cleanup',
    'corehq.apps.cloudcare',
    'corehq.apps.smsbillables',
    'corehq.apps.accounting',
    'corehq.apps.appstore',
    'corehq.apps.domain',
    'corehq.apps.domainsync',
    'corehq.apps.hqadmin',
    'corehq.apps.hqcase',
    'corehq.apps.hqcouchlog',
    'corehq.apps.hqwebapp',
    'corehq.apps.hqmedia',
    'corehq.apps.loadtestendpoints',
    'corehq.apps.locations',
    'corehq.apps.commtrack',
    'corehq.apps.consumption',
    'couchforms',
    'couchexport',
    'couchlog',
    'ctable',
    'ctable_view',
    'dimagi.utils',
    'formtranslate',
    'langcodes',
    'corehq.apps.adm',
    'corehq.apps.announcements',
    'corehq.apps.callcenter',
    'corehq.apps.crud',
    'corehq.apps.receiverwrapper',
    'corehq.apps.migration',
    'corehq.apps.app_manager',
    'corehq.apps.es',
    'corehq.apps.facilities',
    'corehq.apps.fixtures',
    'corehq.apps.importer',
    'corehq.apps.reminders',
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
    'corehq.apps.twilio',
    'corehq.apps.megamobile',
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
    'corehq.apps.cachehq',
    'corehq.apps.toggle_ui',
    'corehq.apps.sofabed',
    'corehq.apps.hqpillow_retry',
    'corehq.couchapps',
    'corehq.preindex',
    'custom.apps.wisepill',
    'custom.fri',
    'fluff',
    'fluff.fluff_filter',
    'soil',
    'toggle',
    'touchforms.formplayer',
    'phonelog',
    'hutch',
    'pillowtop',
    'pillow_retry',
    'corehq.apps.style',
    'corehq.apps.grapevine',

    # custom reports
    'a5288',
    'custom.bihar',
    'custom.penn_state',
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
    'custom.openlmis',
    'custom.ilsgateway',
    'custom.m4change',
    'custom.succeed',

    'custom.uth',

    'custom.colalife',
    'custom.intrahealth',
)

TEST_APPS = ()

# also excludes any app starting with 'django.'
APPS_TO_EXCLUDE_FROM_TESTS = (
    'a5288',
    'couchdbkit.ext.django',
    'corehq.apps.data_interfaces',
    'corehq.apps.ivr',
    'corehq.apps.mach',
    'corehq.apps.ota',
    'corehq.apps.settings',
    'corehq.apps.sislog',
    'corehq.apps.telerivet',
    'corehq.apps.tropo',
    'corehq.apps.megamobile',
    'corehq.apps.yo',
    'crispy_forms',
    'django_extensions',
    'django_prbac',
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
    'custom.apps.crs_reports',
    'custom.m4change',
    'custom.succeed'

    # submodules with tests that run on travis
    'casexml.apps.case',
    'casexml.apps.phone',
    'couchforms',
    'couchexport',
    'ctable',
    'ctable_view',
    'dimagi.utils',
    'fluff',
    'fluff_filter',
    'freddy',
    'pillowtop',
)

INSTALLED_APPS = DEFAULT_APPS + HQ_APPS


# after login, django redirects to this URL
# rather than the default 'accounts/profile'
LOGIN_REDIRECT_URL = '/'

REPORT_CACHE = 'default'  # or e.g. 'redis'

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


####### Shared/Global/UI Settings #######

# restyle some templates
BASE_TEMPLATE = "hqwebapp/base.html"
BASE_ASYNC_TEMPLATE = "reports/async/basic.html"
LOGIN_TEMPLATE = "login_and_password/login.html"
LOGGEDOUT_TEMPLATE = LOGIN_TEMPLATE

# email settings: these ones are the custom hq ones
EMAIL_LOGIN = "user@domain.com"
EMAIL_PASSWORD = "changeme"
EMAIL_SMTP_HOST = "smtp.gmail.com"
EMAIL_SMTP_PORT = 587

# put email addresses here to have them receive bug reports
BUG_REPORT_RECIPIENTS = ()
EXCHANGE_NOTIFICATION_RECIPIENTS = []

# the physical server emailing - differentiate if needed
SERVER_EMAIL = 'commcarehq-noreply@dimagi.com'
DEFAULT_FROM_EMAIL = 'commcarehq-noreply@dimagi.com'
SUPPORT_EMAIL = "commcarehq-support@dimagi.com"
CCHQ_BUG_REPORT_EMAIL = 'commcarehq-bug-reports@dimagi.com'
BILLING_EMAIL = 'billing-comm@dimagi.com'
INVOICING_CONTACT_EMAIL = 'accounts@dimagi.com'
BOOKKEEPER_CONTACT_EMAILS = []
EMAIL_SUBJECT_PREFIX = '[commcarehq] '

SERVER_ENVIRONMENT = 'localdev'

PAGINATOR_OBJECTS_PER_PAGE = 15
PAGINATOR_MAX_PAGE_LINKS = 5

# OpenRosa Standards
OPENROSA_VERSION = "1.0"

# OTA restore fixture generators
FIXTURE_GENERATORS = [
    "corehq.apps.fixtures.fixturegenerators.hq_fixtures",
]

HQ_FIXTURE_GENERATORS = [
    # core
    "corehq.apps.users.fixturegenerators.user_groups",
    "corehq.apps.fixtures.fixturegenerators.item_lists",
    "corehq.apps.reportfixtures.fixturegenerators.indicators",
    "corehq.apps.commtrack.fixtures.product_fixture_generator",
    "corehq.apps.commtrack.fixtures.program_fixture_generator",
    "corehq.apps.locations.fixtures.location_fixture_generator",
    # custom
    "custom.bihar.reports.indicators.fixtures.generator",
    "custom.m4change.fixtures.report_fixtures.generator",
    "custom.m4change.fixtures.location_fixtures.generator",
]

GET_URL_BASE = 'dimagi.utils.web.get_url_base'

SMS_GATEWAY_URL = "http://localhost:8001/"
SMS_GATEWAY_PARAMS = "user=my_username&password=my_password&id=%(phone_number)s&text=%(message)s"

# celery
BROKER_URL = 'django://'  # default django db based

CELERY_MAIN_QUEUE = 'celery'

# this is the default celery queue
# for periodic tasks on a separate queue override this to something else
CELERY_PERIODIC_QUEUE = CELERY_MAIN_QUEUE

# This is the celery queue to use for running reminder rules.
# It's set to the main queue here and can be overridden to put it
# on its own queue.
CELERY_REMINDER_RULE_QUEUE = CELERY_MAIN_QUEUE

SKIP_SOUTH_TESTS = True
#AUTH_PROFILE_MODULE = 'users.HqUserProfile'
TEST_RUNNER = 'testrunner.TwoStageTestRunner'
# this is what gets appended to @domain after your accounts
HQ_ACCOUNT_ROOT = "commcarehq.org"

XFORMS_PLAYER_URL = "http://localhost:4444/"  # touchform's setting
OFFLINE_TOUCHFORMS_PORT = 4444

####### Couchlog config #######

COUCHLOG_BLUEPRINT_HOME = "%s%s" % (
    STATIC_URL, "hqwebapp/stylesheets/blueprint/")
COUCHLOG_DATATABLES_LOC = "%s%s" % (
    STATIC_URL, "hqwebapp/js/lib/datatables-1.9/js/jquery.dataTables.min.js")

COUCHLOG_JQMODAL_LOC = "%s%s" % (STATIC_URL, "hqwebapp/js/lib/jqModal.js")
COUCHLOG_JQMODAL_CSS_LOC = "%s%s" % (
    STATIC_URL, "hqwebapp/stylesheets/jqModal.css")

# These allow HQ to override what shows up in couchlog (add a domain column)
COUCHLOG_TABLE_CONFIG = {"id_column": 0,
                         "archived_column": 1,
                         "date_column": 2,
                         "message_column": 4,
                         "actions_column": 8,
                         "email_column": 9,
                         "no_cols": 10}
COUCHLOG_DISPLAY_COLS = ["id", "archived?", "date", "exception type", "message",
                         "domain", "user", "url", "actions", "report"]
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

####### SMS Queue Settings #######

# Setting this to False will make the system process outgoing and incoming SMS
# immediately rather than use the queue.
SMS_QUEUE_ENABLED = False

# If an SMS still has not been processed in this number of minutes, enqueue it
# again.
SMS_QUEUE_ENQUEUING_TIMEOUT = 60

# Number of minutes a celery task will alot for itself (via lock timeout)
SMS_QUEUE_PROCESSING_LOCK_TIMEOUT = 5

# Number of minutes to wait before retrying an unsuccessful processing attempt
# for a single SMS
SMS_QUEUE_REPROCESS_INTERVAL = 5

# Max number of processing attempts before giving up on processing the SMS
SMS_QUEUE_MAX_PROCESSING_ATTEMPTS = 3

# Number of minutes to wait before retrying SMS that was delayed because the
# domain restricts sending SMS to certain days/times.
SMS_QUEUE_DOMAIN_RESTRICTED_RETRY_INTERVAL = 15

# The number of hours to wait before counting a message as stale. Stale
# messages will not be processed.
SMS_QUEUE_STALE_MESSAGE_DURATION = 7 * 24


####### Pillow Retry Queue Settings #######

# Setting this to False no pillowtop errors will get processed.
PILLOW_RETRY_QUEUE_ENABLED = False

# If an error still has not been processed in this number of minutes, enqueue it
# again.
PILLOW_RETRY_QUEUE_ENQUEUING_TIMEOUT = 60

# Number of minutes a celery task will alot for itself (via lock timeout)
PILLOW_RETRY_PROCESSING_LOCK_TIMEOUT = 5

# Number of minutes to wait before retrying an unsuccessful processing attempt
PILLOW_RETRY_REPROCESS_INTERVAL = 5

# Max number of processing attempts before giving up on processing the error
PILLOW_RETRY_QUEUE_MAX_PROCESSING_ATTEMPTS = 3

# The backoff factor by which to increase re-process intervals by.
# next_interval = PILLOW_RETRY_REPROCESS_INTERVAL * attempts^PILLOW_RETRY_BACKOFF_FACTOR
PILLOW_RETRY_BACKOFF_FACTOR = 2


####### auditcare parameters #######
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

OPEN_EXCHANGE_RATES_ID = ''

# for touchforms maps
GMAPS_API_KEY = "changeme"

# for touchforms authentication
TOUCHFORMS_API_USER = "changeme"
TOUCHFORMS_API_PASSWORD = "changeme"

# import local settings if we find them
LOCAL_APPS = ()
LOCAL_COUCHDB_APPS = ()
LOCAL_MIDDLEWARE_CLASSES = ()
LOCAL_PILLOWTOPS = {}

# If there are existing doc_ids and case_ids you want to check directly,
# they are referenced in your localsettings for more accurate direct checks,
# otherwise use view-based which can be inaccurate.
ES_CASE_CHECK_DIRECT_DOC_ID = None
ES_XFORM_CHECK_DIRECT_DOC_ID = None

# our production logstash aggregation
LOGSTASH_DEVICELOG_PORT = 10777
LOGSTASH_COUCHLOG_PORT = 10888
LOGSTASH_AUDITCARE_PORT = 10999
LOGSTASH_HOST = 'localhost'

# on both a single instance or distributed setup this should assume localhost
ELASTICSEARCH_HOST = 'localhost'
ELASTICSEARCH_PORT = 9200

####### Couch Config #######
# for production this ought to be set to true on your configured couch instance
COUCH_HTTPS = False
COUCH_SERVER_ROOT = 'localhost:5984'  # 6984 for https couch
COUCH_USERNAME = ''
COUCH_PASSWORD = ''
COUCH_DATABASE_NAME = 'commcarehq'

BITLY_LOGIN = ''
BITLY_APIKEY = ''

# this should be overridden in localsettings
INTERNAL_DATA = defaultdict(list)

COUCH_STALE_QUERY = 'update_after'  # 'ok' for cloudant


MESSAGE_LOG_OPTIONS = {
    "abbreviated_phone_number_domains": ["mustmgh", "mgh-cgh-uganda"],
}

IVR_OUTBOUND_RETRIES = 3
IVR_OUTBOUND_RETRY_INTERVAL = 10

# List of Fluff pillow classes that ctable should process diffs for
# deprecated - use IndicatorDocument.save_direct_to_sql
FLUFF_PILLOW_TYPES_TO_SQL = {
    'UnicefMalawiFluff': 'SQL',
    'MalariaConsortiumFluff': 'SQL',
    'CareSAFluff': 'SQL',
    'OpmUserFluff': 'SQL',
}

PREVIEWER_RE = '^$'

MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'

DIGEST_LOGIN_FACTORY = 'django_digest.NoEmailLoginFactory'

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
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
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
        'accountinglog': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'formatter': 'verbose',
            'filename': ACCOUNTING_LOG_FILE
        },
        'couchlog': {
            'level': 'WARNING',
            'class': 'couchlog.handlers.CouchHandler',
        },
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
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
            'handlers': ['console', 'file', 'couchlog', 'sentry'],
            'level': 'INFO',
            'propagate': True
        },
        'pillowtop': {
            'handlers': ['pillowtop', 'sentry'],
            'level': 'ERROR',
            'propagate': False,
        },
        'pillowtop_eval': {
            'handlers': ['sentry'],
            'level': 'INFO',
            'propagate': False,
        },
        'smsbillables': {
            'handlers': ['file', 'sentry'],
            'level': 'ERROR',
            'propagate': False,
        },
        'currency_update': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False,
        },
        'accounting': {
            'handlers': ['accountinglog', 'sentry', 'console', 'couchlog', 'mail_admins'],
            'level': 'INFO',
            'propagate': False,
        },
    }
}

# Django Compressor
COMPRESS_PRECOMPILERS = (
   ('text/less', 'corehq.apps.style.precompilers.LessFilter'),
)
COMPRESS_ENABLED = True

LESS_FOR_BOOTSTRAP_3_BINARY = '/opt/lessc/bin/lessc'

# Invoicing
INVOICE_STARTING_NUMBER = 0
INVOICE_PREFIX = ''
INVOICE_TERMS = ''
INVOICE_FROM_ADDRESS = {}
BANK_ADDRESS = {}
BANK_NAME = ''
BANK_ACCOUNT_NUMBER = ''
BANK_ROUTING_NUMBER = ''
BANK_SWIFT_CODE = ''

STRIPE_PUBLIC_KEY = ''
STRIPE_PRIVATE_KEY = ''

# Mailchimp
MAILCHIMP_APIKEY = ''
MAILCHIMP_COMMCARE_USERS_ID = ''
MAILCHIMP_MASS_EMAIL_ID = ''

SQL_REPORTING_DATABASE_URL = None

try:
    # try to see if there's an environmental variable set for local_settings
    if os.environ.get('CUSTOMSETTINGS', None) == "demo":
        # this sucks, but is a workaround for supporting different settings
        # in the same environment
        from settings_demo import *
    else:
        from localsettings import *
except ImportError:
    pass

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
else:
    TEMPLATE_LOADERS = [
        ('django.template.loaders.cached.Loader', TEMPLATE_LOADERS),
    ]

### Reporting database - use same DB as main database
db_settings = DATABASES["default"].copy()
db_settings['PORT'] = db_settings.get('PORT', '5432')
options = db_settings.get('OPTIONS')
db_settings['OPTIONS'] = '?{}'.format(urlencode(options)) if options else ''

if UNIT_TESTING:
    db_settings['NAME'] = 'test_{}'.format(db_settings['NAME'])

if not SQL_REPORTING_DATABASE_URL or UNIT_TESTING:
    SQL_REPORTING_DATABASE_URL = "postgresql+psycopg2://{USER}:{PASSWORD}@{HOST}:{PORT}/{NAME}{OPTIONS}".format(
        **db_settings
    )

####### South Settings #######
#SKIP_SOUTH_TESTS=True
#SOUTH_TESTS_MIGRATE=False

####### Couch Forms & Couch DB Kit Settings #######
from settingshelper import get_dynamic_db_settings, make_couchdb_tuples

_dynamic_db_settings = get_dynamic_db_settings(
    COUCH_SERVER_ROOT,
    COUCH_USERNAME,
    COUCH_PASSWORD,
    COUCH_DATABASE_NAME,
    use_https=COUCH_HTTPS,
)

# create local server and database configs
COUCH_SERVER = _dynamic_db_settings["COUCH_SERVER"]
COUCH_DATABASE = _dynamic_db_settings["COUCH_DATABASE"]

COUCHDB_APPS = [
    'adm',
    'announcements',
    'api',
    'app_manager',
    'appstore',
    'orgs',
    'builds',
    'case',
    'callcenter',
    'cleanup',
    'cloudcare',
    'commtrack',
    'consumption',
    'couch',
    # This is necessary for abstract classes in dimagi.utils.couch.undo;
    # otherwise breaks tests
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
    'reports',
    'sofabed',
    'sms',
    'smsforms',
    'telerivet',
    'toggle',
    'translations',
    'users',
    'utils',  # dimagi-utils
    'formplayer',
    'phonelog',
    'registration',
    'hutch',
    'wisepill',
    'fri',
    'crs_reports',
    'grapevine',
    'uth',

    # custom reports
    'penn_state',
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
    'accounting',
    'succeed',
    'ilsgateway',
    ('auditcare', 'auditcare'),
    ('couchlog', 'couchlog'),
    ('receiverwrapper', 'receiverwrapper'),
    # needed to make couchdbkit happy
    ('fluff', 'fluff-bihar'),
    ('bihar', 'fluff-bihar'),
    ('opm_reports', 'fluff-opm'),
    ('fluff', 'fluff-opm'),
    ('care_sa', 'fluff-care_sa'),
    ('cvsu', 'fluff-cvsu'),
    ('mc', 'fluff-mc'),
    ('m4change', 'm4change'),
]

COUCHDB_APPS += LOCAL_COUCHDB_APPS

COUCHDB_DATABASES = make_couchdb_tuples(COUCHDB_APPS, COUCH_DATABASE)

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
DEFAULT_CURRENCY_SYMBOL = "$"

SMS_HANDLERS = [
    'corehq.apps.sms.handlers.forwarding.forwarding_handler',
    'corehq.apps.commtrack.sms.handle',
    'corehq.apps.sms.handlers.keyword.sms_keyword_handler',
    'corehq.apps.sms.handlers.form_session.form_session_handler',
    'corehq.apps.sms.handlers.fallback.fallback_handler',
]

SMS_LOADED_BACKENDS = [
    "corehq.apps.unicel.api.UnicelBackend",
    "corehq.apps.mach.api.MachBackend",
    "corehq.apps.tropo.api.TropoBackend",
    "corehq.apps.sms.backend.http_api.HttpBackend",
    "corehq.apps.telerivet.models.TelerivetBackend",
    "corehq.apps.sms.test_backend.TestSMSBackend",
    "corehq.apps.sms.backend.test.TestBackend",
    "corehq.apps.grapevine.api.GrapevineBackend",
    "corehq.apps.twilio.models.TwilioBackend",
    "corehq.apps.megamobile.api.MegamobileBackend",
]

IVR_BACKEND_MAP = {
    "91": "MOBILE_BACKEND_KOOKOO",
}

# The number of seconds to use as a timeout when making gateway requests
SMS_GATEWAY_TIMEOUT = 30
IVR_GATEWAY_TIMEOUT = 60

# These are functions that can be called
# to retrieve custom content in a reminder event.
# If the function is not in here, it will not be called.
ALLOWED_CUSTOM_CONTENT_HANDLERS = {
    "FRI_SMS_CONTENT": "custom.fri.api.custom_content_handler",
    "FRI_SMS_CATCHUP_CONTENT": "custom.fri.api.catchup_custom_content_handler",
    "FRI_SMS_SHIFT": "custom.fri.api.shift_custom_content_handler",
    "FRI_SMS_OFF_DAY": "custom.fri.api.off_day_custom_content_handler",
}

# These are custom templates which can wrap default the sms/chat.html template
CUSTOM_CHAT_TEMPLATES = {
    "FRI": "fri/chat.html",
}

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

PILLOWTOPS = {
    'core': [
        'corehq.pillows.case.CasePillow',
        'corehq.pillows.xform.XFormPillow',
        'corehq.pillows.domain.DomainPillow',
        'corehq.pillows.user.UserPillow',
        'corehq.pillows.application.AppPillow',
        'corehq.pillows.group.GroupPillow',
        'corehq.pillows.sms.SMSPillow',
        'corehq.pillows.user.GroupToUserPillow',
        'corehq.pillows.user.UnknownUsersPillow',
        'corehq.pillows.formdata.FormDataPillow',
    ],
    'phonelog': [
        'corehq.pillows.log.PhoneLogPillow',
    ],
    'core_ext': [
        'corehq.pillows.reportcase.ReportCasePillow',
        'corehq.pillows.reportxform.ReportXFormPillow',
    ],
    'cache': [
        'corehq.pillows.cacheinvalidate.CacheInvalidatePillow',
    ],
    'fluff': [
        'custom.bihar.models.CareBiharFluffPillow',
        'custom.opm.opm_reports.models.OpmCaseFluffPillow',
        'custom.opm.opm_reports.models.OpmUserFluffPillow',
        'custom.opm.opm_reports.models.OpmFormFluffPillow',
        'custom.opm.opm_reports.models.OpmHealthStatusAllInfoFluffPillow',
        'custom.apps.cvsu.models.UnicefMalawiFluffPillow',
        'custom.reports.care_sa.models.CareSAFluffPillow',
        'custom.reports.mc.models.MalariaConsortiumFluffPillow',
        'custom.m4change.models.AncHmisCaseFluffPillow',
        'custom.m4change.models.LdHmisCaseFluffPillow',
        'custom.m4change.models.ImmunizationHmisCaseFluffPillow',
        'custom.m4change.models.ProjectIndicatorsCaseFluffPillow',
        'custom.m4change.models.McctMonthlyAggregateFormFluffPillow',
        'custom.m4change.models.AllHmisCaseFluffPillow',
        'custom.intrahealth.models.CouvertureFluffPillow',
        'custom.intrahealth.models.TauxDeSatisfactionFluffPillow',
        'custom.intrahealth.models.IntraHealthFluffPillow',
        'custom.intrahealth.models.RecapPassagePillow'
    ],
    'mvp': [
        'corehq.apps.indicators.pillows.FormIndicatorPillow',
        'corehq.apps.indicators.pillows.CaseIndicatorPillow',
    ],
    'trialconnect': [
        'custom.trialconnect.smspillow.TCSMSPillow',
    ],
}

for k, v in LOCAL_PILLOWTOPS.items():
    plist = PILLOWTOPS.get(k, [])
    plist.extend(v)
    PILLOWTOPS[k] = plist

COUCH_CACHE_BACKENDS = [
    'corehq.apps.cachehq.cachemodels.DomainGenerationCache',
    'corehq.apps.cachehq.cachemodels.OrganizationGenerationCache',
    'corehq.apps.cachehq.cachemodels.UserGenerationCache',
    'corehq.apps.cachehq.cachemodels.GroupGenerationCache',
    'corehq.apps.cachehq.cachemodels.UserRoleGenerationCache',
    'corehq.apps.cachehq.cachemodels.TeamGenerationCache',
    'corehq.apps.cachehq.cachemodels.ReportGenerationCache',
    'corehq.apps.cachehq.cachemodels.DefaultConsumptionGenerationCache',
    'corehq.apps.cachehq.cachemodels.LocationGenerationCache',
    'corehq.apps.cachehq.cachemodels.DomainInvitationGenerationCache',
    'corehq.apps.cachehq.cachemodels.CommtrackConfigGenerationCache',
    'dimagi.utils.couch.cache.cache_core.gen.GlobalCache',
]

# Custom fully indexed domains for ReportCase index/pillowtop
# Adding a domain will not automatically index that domain's existing cases
ES_CASE_FULL_INDEX_DOMAINS = [
    'pact',
    'hsph',
    'care-bihar',
    'bihar',
    'hsph-dev',
    'hsph-betterbirth-pilot-2',
    'commtrack-public-demo',
    'uth-rhd-test',
    'crs-remind',
    'succeed',
    'opm',
]

# Custom fully indexed domains for ReportXForm index/pillowtop --
# only those domains that don't require custom pre-processing before indexing,
# otherwise list in XFORM_PILLOW_HANDLERS
# Adding a domain will not automatically index that domain's existing forms
ES_XFORM_FULL_INDEX_DOMAINS = [
    'commtrack-public-demo',
    'pact',
    'uth-rhd-test',
    'succeed'
]

CUSTOM_MODULES = [
    'custom.apps.crs_reports',
]

REMOTE_APP_NAMESPACE = "%(domain)s.commcarehq.org"

# mapping of domains to modules for those that aren't identical
# a DOMAIN_MODULE_CONFIG doc present in your couchdb can override individual
# items.
DOMAIN_MODULE_MAP = {
    'a5288-test': 'a5288',
    'a5288-study': 'a5288',
    'care-bihar': 'custom.bihar',
    'bihar': 'custom.bihar',
    'care-ihapc-live': 'custom.reports.care_sa',
    'cvsulive': 'custom.apps.cvsu',
    'dca-malawi': 'dca',
    'eagles-fahu': 'dca',
    'fri': 'custom.fri.reports',
    'fri-testing': 'custom.fri.reports',
    'gsid': 'custom.apps.gsid',
    'gsid-demo': 'custom.apps.gsid',
    'hsph-dev': 'hsph',
    'hsph-betterbirth-pilot-2': 'hsph',
    'mc-inscale': 'custom.reports.mc',
    'psu-legacy-together': 'custom.penn_state',
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
    'ipm-senegal': 'custom.intrahealth',
    'testing-ipm-senegal': 'custom.intrahealth',

    'crs-remind': 'custom.apps.crs_reports',

    'm4change': 'custom.m4change',
    'succeed': 'custom.succeed',
    'test-pathfinder': 'custom.m4change'
}

CASEXML_FORCE_DOMAIN_CHECK = True

# arbitrarily split up tests into three chunks
# that have approximately equal run times,
# The two groups shown here, plus a third group consisting of everything else
TRAVIS_TEST_GROUPS = (
    (
        'accounting', 'adm', 'announcements', 'api', 'app_manager', 'appstore',
        'auditcare', 'bihar', 'builds', 'cachehq', 'callcenter', 'care_benin',
    ),
    (
        'care_sa', 'case', 'cleanup', 'cloudcare', 'commtrack', 'consumption',
        'couchapps', 'couchlog', 'crud', 'cvsu', 'dca', 'django_digest',
        'djangocouch', 'djangocouchuser', 'domain', 'domainsync', 'export',
        'facilities', 'fixtures', 'fluff_filter', 'formplayer',
        'formtranslate', 'fri', 'grapevine', 'groups', 'gsid', 'hope',
        'hqadmin', 'hqcase', 'hqcouchlog', 'hqmedia',
    ),
)

#### Django Compressor Stuff after localsettings overrides ####

# This makes sure that Django Compressor does not run at all
# when LESS_DEBUG is set to True.
if LESS_DEBUG:
    COMPRESS_ENABLED = False
    COMPRESS_PRECOMPILERS = ()

COMPRESS_OFFLINE_CONTEXT = {
    'base_template': BASE_TEMPLATE,
    'login_template': LOGIN_TEMPLATE,
    'original_template': BASE_ASYNC_TEMPLATE,
    'less_debug': LESS_DEBUG,
}
