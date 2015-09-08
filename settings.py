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

DEBUG = True
TEMPLATE_DEBUG = DEBUG
LESS_DEBUG = DEBUG
# Enable LESS_WATCH if you want less.js to constantly recompile.
# Useful if you're making changes to the less files and don't want to refresh
# your page.
LESS_WATCH = False

# clone http://github.com/dimagi/Vellum into submodules/formdesigner and use
# this to select various versions of Vellum source on the form designer page.
# Acceptable values:
# None - production mode
# "dev" - use raw vellum source (submodules/formdesigner/src)
# "dev-min" - use built/minified vellum (submodules/formdesigner/_build/src)
VELLUM_DEBUG = None

# gets set to False for unit tests that run without the database
DB_ENABLED = True
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
    ('sw', 'Swahili'),
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

STATICFILES_DIRS = ()

# bleh, why did this submodule have to be removed?
# deploy fails if this item is present and the path does not exist
_formdesigner_path = os.path.join(FILEPATH, 'submodules', 'formdesigner')
if os.path.exists(_formdesigner_path):
    STATICFILES_DIRS += (('formdesigner', _formdesigner_path),)
del _formdesigner_path

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
    'django.middleware.common.BrokenLinkEmailsMiddleware',
    'corehq.middleware.OpenRosaMiddleware',
    'corehq.util.global_request.middleware.GlobalRequestMiddleware',
    'corehq.apps.users.middleware.UsersMiddleware',
    'corehq.apps.domain.middleware.CCHQPRBACMiddleware',
    'corehq.apps.domain.middleware.DomainHistoryMiddleware',
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
    'djcelery',
    'djtables',
    'django_prbac',
    'djkombu',
    'djangular',
    'couchdbkit.ext.django',
    'crispy_forms',
    'gunicorn',
    'raven.contrib.django.raven_compat',
    'compressor',
    'mptt',
    'tastypie',
)

CRISPY_TEMPLATE_PACK = 'bootstrap'
CRISPY_ALLOWED_TEMPLATE_PACKS = (
    'bootstrap',
    'bootstrap3',
)

HQ_APPS = (
    'django_digest',
    'rosetta',
    'auditcare',
    'hqscripts',
    'casexml.apps.case',
    'corehq.apps.casegroups',
    'casexml.apps.phone',
    'casexml.apps.stock',
    'corehq.apps.cleanup',
    'corehq.apps.cloudcare',
    'corehq.apps.smsbillables',
    'corehq.apps.accounting',
    'corehq.apps.appstore',
    'corehq.apps.data_analytics',
    'corehq.apps.domain',
    'corehq.apps.domainsync',
    'corehq.apps.hqadmin',
    'corehq.apps.hqcase',
    'corehq.apps.hqcouchlog',
    'corehq.apps.hqwebapp',
    'corehq.apps.hqmedia',
    'corehq.apps.loadtestendpoints',
    'corehq.apps.locations',
    'corehq.apps.products',
    'corehq.apps.prelogin',
    'corehq.apps.programs',
    'corehq.apps.commtrack',
    'corehq.apps.consumption',
    'corehq.apps.tzmigration',
    'couchforms',
    'couchexport',
    'couchlog',
    'ctable',
    'ctable_view',
    'dimagi.utils',
    'formtranslate',
    'langcodes',
    'corehq.apps.analytics',
    'corehq.apps.callcenter',
    'corehq.apps.crud',
    'corehq.apps.custom_data_fields',
    'corehq.apps.receiverwrapper',
    'corehq.apps.app_manager',
    'corehq.apps.es',
    'corehq.apps.facilities',
    'corehq.apps.fixtures',
    'corehq.apps.importer',
    'corehq.apps.reminders',
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
    'corehq.apps.dropbox',
    'corehq.apps.megamobile',
    'corehq.apps.kookoo',
    'corehq.apps.sislog',
    'corehq.apps.yo',
    'corehq.apps.telerivet',
    'corehq.apps.mach',
    'corehq.apps.performance_sms',
    'corehq.apps.registration',
    'corehq.apps.unicel',
    'corehq.apps.reports',
    'corehq.apps.reports_core',
    'corehq.apps.userreports',
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
    'pillowtop',
    'pillow_retry',
    'corehq.apps.style',
    'corehq.apps.styleguide',
    'corehq.apps.grapevine',
    'corehq.apps.dashboard',
    'corehq.util',
    'dimagi.ext',

    # custom reports
    'a5288',
    'custom.bihar',
    'custom.penn_state',
    'custom.apps.gsid',
    'hsph',
    'mvp',
    'mvp_docs',
    'mvp_indicators',
    'custom.opm',
    'pathindia',
    'pact',

    'custom.apps.care_benin',
    'custom.apps.cvsu',
    'custom.reports.mc',
    'custom.apps.crs_reports',
    'custom.hope',
    'custom.openlmis',
    'custom.logistics',
    'custom.ilsgateway',
    'custom.ewsghana',
    'custom.m4change',
    'custom.succeed',
    'custom.ucla',

    'custom.uth',

    'custom.colalife',
    'custom.intrahealth',
    'custom.world_vision',
    'custom.tdh',
    'custom.up_nrhm',

    'custom.care_pathways',
    'custom.common',

    'custom.dhis2',
    'custom.guinea_backup',
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
    'custom.apps.crs_reports',
    'custom.m4change',

    # submodules with tests that run on travis
    # 'couchexport',
    'ctable',
    'ctable_view',
    'dimagi.utils',
    'fluff',
    'fluff_filter',
    'freddy',
    'pillowtop',
    'pillow_retry',
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
# maintain CommCare HQ/CommCare Supply distinction.
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
BASE_TEMPLATE = "style/bootstrap2/base.html"  # should eventually be bootstrap3
BASE_ASYNC_TEMPLATE = "reports/async/basic.html"
LOGIN_TEMPLATE = "login_and_password/login.html"
LOGGEDOUT_TEMPLATE = LOGIN_TEMPLATE

CSRF_FAILURE_VIEW = 'corehq.apps.hqwebapp.views.csrf_failure'

# These are non-standard setting names that are used in localsettings
# The standard variables are then set to these variables after localsettings
# Todo: Change to use standard settings variables
# Todo: Will require changing salt pillar and localsettings template
# Todo: or more likely in ansible once that's a thing
EMAIL_LOGIN = "user@domain.com"
EMAIL_PASSWORD = "changeme"
EMAIL_SMTP_HOST = "smtp.gmail.com"
EMAIL_SMTP_PORT = 587
# These are the normal Django settings
EMAIL_USE_TLS = True

# put email addresses here to have them receive bug reports
BUG_REPORT_RECIPIENTS = ()
EXCHANGE_NOTIFICATION_RECIPIENTS = []

# the physical server emailing - differentiate if needed
SERVER_EMAIL = 'commcarehq-noreply@dimagi.com'
DEFAULT_FROM_EMAIL = 'commcarehq-noreply@dimagi.com'
SUPPORT_EMAIL = "commcarehq-support@dimagi.com"
PROBONO_SUPPORT_EMAIL = 'billing-support@dimagi.com'
CCHQ_BUG_REPORT_EMAIL = 'commcarehq-bug-reports@dimagi.com'
ACCOUNTS_EMAIL = 'accounts@dimagi.com'
FINANCE_EMAIL = 'finance@dimagi.com'
DATA_EMAIL = 'datatree@dimagi.com'
SUBSCRIPTION_CHANGE_EMAIL = 'accounts+subchange@dimagi.com'
INTERNAL_SUBSCRIPTION_CHANGE_EMAIL = 'accounts+subchange+internal@dimagi.com'
BILLING_EMAIL = 'billing-comm@dimagi.com'
INVOICING_CONTACT_EMAIL = 'billing-support@dimagi.com'
MASTER_LIST_EMAIL = 'master-list@dimagi.com'
EULA_CHANGE_EMAIL = 'eula-notifications@dimagi.com'
CONTACT_EMAIL = 'info@dimagi.com'
BOOKKEEPER_CONTACT_EMAILS = []
EMAIL_SUBJECT_PREFIX = '[commcarehq] '

SERVER_ENVIRONMENT = 'localdev'

PAGINATOR_OBJECTS_PER_PAGE = 15
PAGINATOR_MAX_PAGE_LINKS = 5

# OpenRosa Standards
OPENROSA_VERSION = "1.0"

# OTA restore fixture generators
FIXTURE_GENERATORS = {
    # fixtures that may be sent to the phone independent of cases
    'standalone': [
        # core
        "corehq.apps.users.fixturegenerators.user_groups",
        "corehq.apps.fixtures.fixturegenerators.item_lists",
        "corehq.apps.callcenter.fixturegenerators.indicators_fixture_generator",
        "corehq.apps.products.fixtures.product_fixture_generator",
        "corehq.apps.programs.fixtures.program_fixture_generator",
        "corehq.apps.userreports.fixtures.report_fixture_generator",
        # custom
        "custom.bihar.reports.indicators.fixtures.generator",
        "custom.m4change.fixtures.report_fixtures.generator",
        "custom.m4change.fixtures.location_fixtures.generator",
    ],
    # fixtures that must be sent along with the phones cases
    'case': [
        "corehq.apps.locations.fixtures.location_fixture_generator",
    ]
}

### Shared drive settings ###
# Also see section after localsettings import
SHARED_DRIVE_ROOT = None

# name of the directory within SHARED_DRIVE_ROOT
RESTORE_PAYLOAD_DIR_NAME = None

# name of the directory within SHARED_DRIVE_ROOT
SHARED_TEMP_DIR_NAME = None

## django-transfer settings
# These settings must match the apache / nginx config
TRANSFER_SERVER = None  # 'apache' or 'nginx'
# name of the directory within SHARED_DRIVE_ROOT
TRANSFER_FILE_DIR_NAME = None

GET_URL_BASE = 'dimagi.utils.web.get_url_base'

SMS_GATEWAY_URL = "http://localhost:8001/"
SMS_GATEWAY_PARAMS = "user=my_username&password=my_password&id=%(phone_number)s&text=%(message)s"

# celery
BROKER_URL = 'django://'  # default django db based

from settingshelper import celery_failure_handler

CELERY_ANNOTATIONS = {'*': {'on_failure': celery_failure_handler}}

CELERY_MAIN_QUEUE = 'celery'

# this is the default celery queue
# for periodic tasks on a separate queue override this to something else
CELERY_PERIODIC_QUEUE = CELERY_MAIN_QUEUE

# This is the celery queue to use for running reminder rules.
# It's set to the main queue here and can be overridden to put it
# on its own queue.
CELERY_REMINDER_RULE_QUEUE = CELERY_MAIN_QUEUE

# This is the celery queue to use for running reminder case updates.
# It's set to the main queue here and can be overridden to put it
# on its own queue.
CELERY_REMINDER_CASE_UPDATE_QUEUE = CELERY_MAIN_QUEUE

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
COUCHLOG_AUTH_DECORATOR = 'corehq.apps.domain.decorators.require_superuser_or_developer'

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


####### Reminders Queue Settings #######

# Setting this to False will make the system fire reminders every
# minute on the periodic queue. Setting to True will queue up reminders
# on the reminders queue.
REMINDERS_QUEUE_ENABLED = False

# If a reminder still has not been processed in this number of minutes, enqueue it
# again.
REMINDERS_QUEUE_ENQUEUING_TIMEOUT = 60

# Number of minutes a celery task will alot for itself (via lock timeout)
REMINDERS_QUEUE_PROCESSING_LOCK_TIMEOUT = 5

# Number of minutes to wait before retrying an unsuccessful processing attempt
# for a single reminder
REMINDERS_QUEUE_REPROCESS_INTERVAL = 5

# Max number of processing attempts before giving up on processing the reminder
REMINDERS_QUEUE_MAX_PROCESSING_ATTEMPTS = 3

# The number of hours to wait before counting a reminder as stale. Stale
# reminders will not be processed.
REMINDERS_QUEUE_STALE_REMINDER_DURATION = 7 * 24


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

# After an error's total attempts exceeds this number it will only be re-attempted
# once after being reset. This is to prevent numerous retries of errors that aren't
# getting fixed
PILLOW_RETRY_MULTI_ATTEMPTS_CUTOFF = PILLOW_RETRY_QUEUE_MAX_PROCESSING_ATTEMPTS * 3

####### auditcare parameters #######
AUDIT_MODEL_SAVE = [
    'corehq.apps.app_manager.Application',
    'corehq.apps.app_manager.RemoteApp',
]

AUDIT_VIEWS = [
    'corehq.apps.settings.views.ChangeMyPasswordView',
    'corehq.apps.hqadmin.views.AuthenticateAs',
]

AUDIT_MODULES = [
    'corehq.apps.reports',
    'corehq.apps.userreports',
    'corehq.apps.data',
    'corehq.apps.registration',
    'tastypie',
]

# Don't use google analytics unless overridden in localsettings
ANALYTICS_IDS = {
    'GOOGLE_ANALYTICS_ID': '',
    'PINGDOM_ID': '',
    'ANALYTICS_ID_PUBLIC_COMMCARE': '',
    'KISSMETRICS_KEY': '',
    'HUBSPOT_API_KEY': '',
    'HUBSPOT_ID': '',
}

ANALYTICS_CONFIG = {
    "HQ_INSTANCE": '',  # e.g. "www" or "staging"
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

# Prelogin site
ENABLE_PRELOGIN_SITE = False
PRELOGIN_APPS = (
    'corehq.apps.prelogin',
)

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
            'class': 'corehq.util.log.HqAdminEmailHandler',
        },
        'notify_exception': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'corehq.util.log.NotifyExceptionEmailer',
        },
        'sentry': {
            'level': 'ERROR',
            'class': 'raven.contrib.django.raven_compat.handlers.SentryHandler',
        },
        'null': {
            'class': 'django.utils.log.NullHandler',
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
        'django.security.DisallowedHost': {
            'handlers': ['null'],
            'propagate': False,
        },
        'notify': {
            'handlers': ['notify_exception'],
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

LESS_B3_PATHS = {
    'variables': '../../../style/less/bootstrap3/includes/variables',
    'mixins': '../../../style/less/bootstrap3/includes/mixins',
}

LESS_FOR_BOOTSTRAP_3_BINARY = '/opt/lessc/bin/lessc'

# Invoicing
INVOICE_STARTING_NUMBER = 0
INVOICE_PREFIX = ''
INVOICE_TERMS = ''
INVOICE_FROM_ADDRESS = {}
BANK_ADDRESS = {}
BANK_NAME = ''
BANK_ACCOUNT_NUMBER = ''
BANK_ROUTING_NUMBER_ACH = ''
BANK_ROUTING_NUMBER_WIRE = ''
BANK_SWIFT_CODE = ''

STRIPE_PUBLIC_KEY = ''
STRIPE_PRIVATE_KEY = ''

# Mailchimp
MAILCHIMP_APIKEY = ''
MAILCHIMP_COMMCARE_USERS_ID = ''
MAILCHIMP_MASS_EMAIL_ID = ''

SQL_REPORTING_DATABASE_URL = None

# number of days since last access after which a saved export is considered unused
SAVED_EXPORT_ACCESS_CUTOFF = 35

# override for production
DEFAULT_PROTOCOL = 'http'

# Dropbox
DROPBOX_KEY = ''
DROPBOX_SECRET = ''
DROPBOX_APP_NAME = ''


try:
    # try to see if there's an environmental variable set for local_settings
    if os.environ.get('CUSTOMSETTINGS', None) == "demo":
        # this sucks, but is a workaround for supporting different settings
        # in the same environment
        from settings_demo import *
    else:
        from localsettings import *
        if globals().get("FIX_LOGGER_ERROR_OBFUSCATION"):
            # this is here because the logging config cannot import
            # corehq.util.log.HqAdminEmailHandler, for example, if there
            # is a syntax error in any module imported by corehq/__init__.py
            # Setting FIX_LOGGER_ERROR_OBFUSCATION = True in
            # localsettings.py will reveal the real error.
            # Note that changing this means you will not be able to use/test anything
            # related to email logging.
            for handler in LOGGING["handlers"].values():
                if handler["class"].startswith("corehq."):
                    print "{} logger is being changed to {}".format(
                        handler['class'],
                        'logging.StreamHandler'
                    )
                    handler["class"] = "logging.StreamHandler"
except ImportError:
   # fallback in case nothing else is found - used for readthedocs
   from dev_settings import *

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
    os.environ['PYTHONWARNINGS'] = 'd'  # Show DeprecationWarning
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

MVP_INDICATOR_DB = 'mvp-indicators'

INDICATOR_CONFIG = {
    "mvp-sauri": ['mvp_indicators'],
    "mvp-potou": ['mvp_indicators'],
}

####### Couch Forms & Couch DB Kit Settings #######
from settingshelper import (
    get_dynamic_db_settings,
    make_couchdb_tuples,
    get_extra_couchdbs,
    SharedDriveConfiguration
)

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
    'casegroups',
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
    'custom_data_fields',
    'hqadmin',
    'domain',
    'ext',
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
    'mobile_auth',
    'phone',
    'pillowtop',
    'pillow_retry',
    'products',
    'programs',
    'reminders',
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
    'wisepill',
    'fri',
    'crs_reports',
    'grapevine',
    'uth',
    'dhis2',

    # custom reports
    'penn_state',
    'care_benin',
    'gsid',
    'hsph',
    'mvp',
    ('mvp_docs', MVP_INDICATOR_DB),
    'pathindia',
    'pact',
    'accounting',
    'succeed',
    'ilsgateway',
    'ewsghana',
    ('auditcare', 'auditcare'),
    ('couchlog', 'couchlog'),
    ('performance_sms', 'meta'),
    ('receiverwrapper', 'receiverwrapper'),
    ('userreports', 'meta'),
    ('custom_data_fields', 'meta'),
    # needed to make couchdbkit happy
    ('fluff', 'fluff-bihar'),
    ('bihar', 'fluff-bihar'),
    ('opm', 'fluff-opm'),
    ('fluff', 'fluff-opm'),
    ('cvsu', 'fluff-cvsu'),
    ('mc', 'fluff-mc'),
    ('m4change', 'm4change'),
    ('export', 'meta'),
    'tdhtesting'
]

COUCHDB_APPS += LOCAL_COUCHDB_APPS

COUCHDB_DATABASES = make_couchdb_tuples(COUCHDB_APPS, COUCH_DATABASE)
EXTRA_COUCHDB_DATABASES = get_extra_couchdbs(COUCHDB_APPS, COUCH_DATABASE)

INSTALLED_APPS += LOCAL_APPS

if ENABLE_PRELOGIN_SITE:
    INSTALLED_APPS += PRELOGIN_APPS

seen = set()
INSTALLED_APPS = [x for x in INSTALLED_APPS if x not in seen and not seen.add(x)]

MIDDLEWARE_CLASSES += LOCAL_MIDDLEWARE_CLASSES

### Shared drive settings ###
SHARED_DRIVE_CONF = SharedDriveConfiguration(
    SHARED_DRIVE_ROOT,
    RESTORE_PAYLOAD_DIR_NAME,
    TRANSFER_FILE_DIR_NAME,
    SHARED_TEMP_DIR_NAME
)
TRANSFER_MAPPINGS = {
    SHARED_DRIVE_CONF.transfer_dir: '/{}'.format(TRANSFER_FILE_DIR_NAME),  # e.g. '/mnt/shared/downloads': '/downloads',
}

# these are the official django settings
# which really we should be using over the custom ones
EMAIL_HOST = EMAIL_SMTP_HOST
EMAIL_PORT = EMAIL_SMTP_PORT
EMAIL_HOST_USER = EMAIL_LOGIN
EMAIL_HOST_PASSWORD = EMAIL_PASSWORD
# EMAIL_USE_TLS and SEND_BROKEN_LINK_EMAILS are set above
# so they can be overridden in localsettings (e.g. in a dev environment)

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
    messages.WARNING: 'alert-error alert-danger',
    messages.ERROR: 'alert-error alert-danger',
}

COMMCARE_USER_TERM = "Mobile Worker"
WEB_USER_TERM = "Web User"

DEFAULT_CURRENCY = "USD"
DEFAULT_CURRENCY_SYMBOL = "$"

SMS_HANDLERS = [
    'corehq.apps.sms.handlers.forwarding.forwarding_handler',
    'custom.ilsgateway.tanzania.handler.handle',
    'custom.ewsghana.handler.handle',
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
        'corehq.pillows.sofabed.FormDataPillow',
        'corehq.pillows.sofabed.CaseDataPillow',
    ],
    'phonelog': [
        'corehq.pillows.log.PhoneLogPillow',
    ],
    'core_ext': [
        'corehq.pillows.reportcase.ReportCasePillow',
        'corehq.pillows.reportxform.ReportXFormPillow',
        'corehq.apps.userreports.pillow.ConfigurableIndicatorPillow',
        'corehq.apps.userreports.pillow.StaticDataSourcePillow',
    ],
    'cache': [
        'corehq.pillows.cacheinvalidate.CacheInvalidatePillow',
    ],
    'fluff': [
        'custom.bihar.models.CareBiharFluffPillow',
        'custom.opm.models.OpmCaseFluffPillow',
        'custom.opm.models.OpmUserFluffPillow',
        'custom.opm.models.OpmFormFluffPillow',
        'custom.opm.models.VhndAvailabilityFluffPillow',
        'custom.apps.cvsu.models.UnicefMalawiFluffPillow',
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
        'custom.intrahealth.models.RecapPassagePillow',
        'custom.intrahealth.models.TauxDeRuptureFluffPillow',
        'custom.intrahealth.models.LivraisonFluffPillow',
        'custom.intrahealth.models.RecouvrementFluffPillow',
        'custom.care_pathways.models.GeographyFluffPillow',
        'custom.care_pathways.models.FarmerRecordFluffPillow',
        'custom.world_vision.models.WorldVisionMotherFluffPillow',
        'custom.world_vision.models.WorldVisionChildFluffPillow',
        'custom.world_vision.models.WorldVisionHierarchyFluffPillow',
        'custom.tdh.models.TDHEnrollChildFluffPillow',
        'custom.tdh.models.TDHInfantClassificationFluffPillow',
        'custom.tdh.models.TDHInfantTreatmentFluffPillow',
        'custom.tdh.models.TDHNewbornClassificationFluffPillow',
        'custom.tdh.models.TDHNewbornTreatmentFluffPillow',
        'custom.tdh.models.TDHChildClassificationFluffPillow',
        'custom.tdh.models.TDHChildTreatmentFluffPillow',
        'custom.succeed.models.UCLAPatientFluffPillow',
    ],
    'mvp_indicators': [
        'mvp_docs.pillows.MVPFormIndicatorPillow',
        'mvp_docs.pillows.MVPCaseIndicatorPillow',
    ],
}


STATIC_UCR_REPORTS = [
    os.path.join('custom', '_legacy', 'mvp', 'ucr', 'reports', 'deidentified_va_report.json'),
    os.path.join('custom', 'abt', 'reports', 'incident_report.json')
]


STATIC_DATA_SOURCES = [
    os.path.join('custom', 'up_nrhm', 'data_sources', 'location_hierarchy.json'),
    os.path.join('custom', 'up_nrhm', 'data_sources', 'asha_facilitators.json'),
    os.path.join('custom', 'succeed', 'data_sources', 'submissions.json'),
    os.path.join('custom', 'succeed', 'data_sources', 'patient_task_list.json'),
    os.path.join('custom', 'apps', 'gsid', 'data_sources', 'patient_summary.json'),
    os.path.join('custom', 'abt', 'reports', 'data_sources', 'sms.json'),
    os.path.join('custom', 'abt', 'reports', 'data_sources', 'supervisory.json'),
    os.path.join('custom', '_legacy', 'mvp', 'ucr', 'reports', 'data_sources', 'va_datasource.json'),
]


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
    'corehq.apps.cachehq.cachemodels.UserReportsDataSourceCache',
    'corehq.apps.cachehq.cachemodels.UserReportsReportConfigCache',
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

CUSTOM_UCR_EXPRESSIONS = [
    ('abt_supervisor', 'custom.abt.reports.expressions.abt_supervisor_expression'),
    ('mvp_medical_cause', 'mvp.ucr.reports.expressions.medical_cause_expression'),
    ('mvp_no_treatment_reason', 'mvp.ucr.reports.expressions.no_treatment_reason_expression'),
    ('mvp_treatment_provider_name', 'mvp.ucr.reports.expressions.treatment_provider_name_expression'),
    ('mvp_treatment_place_name', 'mvp.ucr.reports.expressions.treatment_place_name_expression'),
    ('mvp_death_place', 'mvp.ucr.reports.expressions.death_place_expression'),
    ('succeed_referenced_id', 'custom.succeed.expressions.succeed_referenced_id'),
]

CUSTOM_MODULES = [
    'custom.apps.crs_reports',
    'custom.ilsgateway',
    'custom.ewsghana',
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
    'cvsulive': 'custom.apps.cvsu',
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
    'mvp-tiby': 'mvp',
    'mvp-mbola': 'mvp',
    'mvp-koraro': 'mvp',
    'mvp-pampaida': 'mvp',
    'opm': 'custom.opm',
    'project': 'custom.apps.care_benin',

    'ipm-senegal': 'custom.intrahealth',
    'testing-ipm-senegal': 'custom.intrahealth',
    'up-nrhm': 'custom.up_nrhm',

    'crs-remind': 'custom.apps.crs_reports',

    'm4change': 'custom.m4change',
    'succeed': 'custom.succeed',
    'ilsgateway-test-1': 'custom.ilsgateway',
    'ilsgateway-test-2': 'custom.ilsgateway',
    'ewsghana-test-1': 'custom.ewsghana',
    'ewsghana-test-2': 'custom.ewsghana',
    'test-pathfinder': 'custom.m4change',
    'wvindia2': 'custom.world_vision',
    'pathways-india-mis': 'custom.care_pathways',
    'pathways-tanzania': 'custom.care_pathways',
    'tdhtesting': 'custom.tdh',
    'rec': 'custom.tdh'
}

CASEXML_FORCE_DOMAIN_CHECK = True

# arbitrarily split up tests into two chunks
# that have approximately equal run times,
# the group shown here, plus a second group consisting of everything else
TRAVIS_TEST_GROUPS = (
    (
        'accounting', 'adm', 'announcements', 'api', 'app_manager', 'appstore',
        'auditcare', 'bihar', 'builds', 'cachehq', 'callcenter', 'care_benin',
        'case', 'casegroups', 'cleanup', 'cloudcare', 'commtrack', 'consumption',
        'couchapps', 'couchlog', 'crud', 'cvsu', 'django_digest',
        'domain', 'domainsync', 'export',
        'facilities', 'fixtures', 'fluff_filter', 'formplayer',
        'formtranslate', 'fri', 'grapevine', 'groups', 'gsid', 'hope',
        'hqadmin', 'hqcase', 'hqcouchlog', 'hqmedia',
        'care_pathways', 'colalife', 'common', 'compressor',
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
    'less_watch': LESS_WATCH,
}

COMPRESS_CSS_HASHING_METHOD = 'content'
