#!/usr/bin/env python
import importlib
from collections import defaultdict

import os
from urllib import urlencode
from django.contrib import messages
import settingshelper as helper

# odd celery fix
import djcelery

djcelery.setup_loader()

DEBUG = True
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

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# gets set to False for unit tests that run without the database
DB_ENABLED = True
UNIT_TESTING = helper.is_testing()

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
    ('es', 'Spanish'),
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
STATIC_CDN = ''

FILEPATH = BASE_DIR
SERVICE_DIR = os.path.join(FILEPATH, 'deployment', 'commcare-hq-deploy', 'fab', 'services', 'templates')
# media for user uploaded media.  in general this won't be used at all.
MEDIA_ROOT = os.path.join(FILEPATH, 'mediafiles')
STATIC_ROOT = os.path.join(FILEPATH, 'staticfiles')


# Django i18n searches for translation files (django.po) within this dir
# and then in the locale/ directories of installed apps
LOCALE_PATHS = (
    os.path.join(FILEPATH, 'locale'),
)

BOWER_COMPONENTS = os.path.join(FILEPATH, 'bower_components')

STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    'compressor.finders.CompressorFinder',
)

STATICFILES_DIRS = (
    BOWER_COMPONENTS,
)

# bleh, why did this submodule have to be removed?
# deploy fails if this item is present and the path does not exist
_formdesigner_path = os.path.join(FILEPATH, 'submodules', 'formdesigner')
if os.path.exists(_formdesigner_path):
    STATICFILES_DIRS += (('formdesigner', _formdesigner_path),)
del _formdesigner_path

LOG_HOME = FILEPATH
COUCH_LOG_FILE = "%s/%s" % (FILEPATH, "commcarehq.django.log")
DJANGO_LOG_FILE = "%s/%s" % (FILEPATH, "commcarehq.django.log")
ACCOUNTING_LOG_FILE = "%s/%s" % (FILEPATH, "commcarehq.accounting.log")
ANALYTICS_LOG_FILE = "%s/%s" % (FILEPATH, "commcarehq.analytics.log")
DATADOG_LOG_FILE = "%s/%s" % (FILEPATH, "commcarehq.datadog.log")
UCR_TIMING_FILE = "%s/%s" % (FILEPATH, "ucr.timing.log")
UCR_DIFF_FILE = "%s/%s" % (FILEPATH, "ucr.diff.log")
UCR_EXCEPTION_FILE = "%s/%s" % (FILEPATH, "ucr.exception.log")
NIKSHAY_DATAMIGRATION = "%s/%s" % (FILEPATH, "nikshay_datamigration.log")

LOCAL_LOGGING_HANDLERS = {}
LOCAL_LOGGING_LOGGERS = {}

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/static/admin/'

# Make this unique, and don't share it with anybody - put into localsettings.py
SECRET_KEY = 'you should really change this'

# Add this to localsettings and set it to False, so that CSRF protection is enabled on localhost
CSRF_SOFT_MODE = True

MIDDLEWARE_CLASSES = [
    'corehq.middleware.NoCacheMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.common.BrokenLinkEmailsMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'corehq.middleware.OpenRosaMiddleware',
    'corehq.util.global_request.middleware.GlobalRequestMiddleware',
    'corehq.apps.users.middleware.UsersMiddleware',
    'corehq.apps.domain.middleware.DomainMigrationMiddleware',
    'corehq.middleware.TimeoutMiddleware',
    'corehq.apps.domain.middleware.CCHQPRBACMiddleware',
    'corehq.apps.domain.middleware.DomainHistoryMiddleware',
    'casexml.apps.phone.middleware.SyncTokenMiddleware',
    'auditcare.middleware.AuditMiddleware',
    'no_exceptions.middleware.NoExceptionsMiddleware',
    'corehq.apps.locations.middleware.LocationAccessMiddleware',
]

SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

# time in minutes before forced logout due to inactivity
INACTIVITY_TIMEOUT = 60 * 24 * 14
SECURE_TIMEOUT = 30
ENABLE_DRACONIAN_SECURITY_FEATURES = False

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
    'djangular',
    'captcha',
    'couchdbkit.ext.django',
    'crispy_forms',
    'gunicorn',
    'compressor',
    'mptt',
    'tastypie',
    'django_otp',
    'django_otp.plugins.otp_static',
    'django_otp.plugins.otp_totp',
    'two_factor',
    'ws4redis',
    'statici18n',
)

CAPTCHA_FIELD_TEMPLATE = 'hq-captcha-field.html'
CRISPY_TEMPLATE_PACK = 'bootstrap3'
CRISPY_ALLOWED_TEMPLATE_PACKS = (
    'bootstrap',
    'bootstrap3',
)

HQ_APPS = (
    'django_digest',
    'auditcare',
    'hqscripts',
    'casexml.apps.case',
    'corehq.apps.casegroups',
    'casexml.apps.phone',
    'casexml.apps.stock',
    'corehq.apps.cleanup',
    'corehq.apps.cloudcare',
    'corehq.apps.couch_sql_migration',
    'corehq.apps.smsbillables',
    'corehq.apps.accounting',
    'corehq.apps.appstore',
    'corehq.apps.data_analytics',
    'corehq.apps.domain',
    'corehq.apps.domainsync',
    'corehq.apps.domain_migration_flags',
    'corehq.apps.dump_reload',
    'corehq.apps.hqadmin',
    'corehq.apps.hqcase',
    'corehq.apps.hqwebapp',
    'corehq.apps.hqmedia',
    'corehq.apps.locations',
    'corehq.apps.products',
    'corehq.apps.prelogin',
    'corehq.apps.programs',
    'corehq.apps.commtrack',
    'corehq.apps.consumption',
    'corehq.apps.tzmigration',
    'corehq.form_processor.app_config.FormProcessorAppConfig',
    'corehq.sql_db',
    'corehq.sql_accessors',
    'corehq.sql_proxy_accessors',
    'couchforms',
    'couchexport',
    'dimagi.utils',
    'formtranslate',
    'langcodes',
    'corehq.apps.data_dictionary',
    'corehq.apps.analytics',
    'corehq.apps.callcenter',
    'corehq.apps.change_feed',
    'corehq.apps.crud',
    'corehq.apps.custom_data_fields',
    'corehq.apps.receiverwrapper',
    'corehq.apps.repeaters',
    'corehq.apps.app_manager',
    'corehq.apps.es',
    'corehq.apps.fixtures',
    'corehq.apps.calendar_fixture',
    'corehq.apps.case_importer',
    'corehq.apps.reminders',
    'corehq.apps.translations',
    'corehq.apps.tour',
    'corehq.apps.users',
    'corehq.apps.settings',
    'corehq.apps.ota',
    'corehq.apps.groups',
    'corehq.apps.mobile_auth',
    'corehq.apps.sms',
    'corehq.apps.smsforms',
    'corehq.apps.ivr',
    'corehq.messaging.smsbackends.tropo',
    'corehq.messaging.smsbackends.twilio',
    'corehq.apps.dropbox',
    'corehq.messaging.smsbackends.megamobile',
    'corehq.messaging.ivrbackends.kookoo',
    'corehq.messaging.smsbackends.sislog',
    'corehq.messaging.smsbackends.yo',
    'corehq.messaging.smsbackends.telerivet',
    'corehq.messaging.smsbackends.mach',
    'corehq.messaging.smsbackends.http',
    'corehq.messaging.smsbackends.smsgh',
    'corehq.messaging.smsbackends.push',
    'corehq.messaging.smsbackends.apposit',
    'corehq.messaging.smsbackends.test',
    'corehq.apps.performance_sms',
    'corehq.apps.registration',
    'corehq.messaging.smsbackends.unicel',
    'corehq.messaging.smsbackends.icds_nic',
    'corehq.apps.reports',
    'corehq.apps.reports_core',
    'corehq.apps.userreports',
    'corehq.apps.data_interfaces',
    'corehq.apps.export',
    'corehq.apps.builds',
    'corehq.apps.api',
    'corehq.apps.indicators',
    'corehq.apps.notifications',
    'corehq.apps.cachehq',
    'corehq.apps.toggle_ui',
    'corehq.apps.hqpillow_retry',
    'corehq.couchapps',
    'corehq.preindex',
    'corehq.tabs',
    'custom.apps.wisepill',
    'custom.fri',
    'custom.openclinica',
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
    'corehq.messaging.smsbackends.grapevine',
    'corehq.apps.dashboard',
    'corehq.util',
    'dimagi.ext',
    'corehq.doctypemigrations',
    'corehq.blobs',
    'corehq.apps.case_search',
    'corehq.apps.zapier.apps.ZapierConfig',

    # custom reports
    'a5288',
    'custom.bihar',
    'custom.apps.gsid',
    'hsph',
    'mvp',
    'mvp_docs',
    'mvp_indicators',
    'custom.opm',
    'pact',

    'custom.reports.mc',
    'custom.apps.crs_reports',
    'custom.hope',
    'custom.logistics',
    'custom.ilsgateway',
    'custom.zipline',
    'custom.ewsghana',
    'custom.m4change',
    'custom.succeed',
    'custom.ucla',

    'custom.uth',

    'custom.intrahealth',
    'custom.world_vision',
    'custom.up_nrhm',

    'custom.care_pathways',
    'custom.common',

    'custom.icds',
    'custom.icds_reports',
    'custom.pnlppgi',
)

ENIKSHAY_APPS = (
    'custom.enikshay',
    'custom.enikshay.integrations.ninetyninedots',
    'custom.enikshay.nikshay_datamigration',
    'custom.enikshay.integrations.nikshay'
)

# DEPRECATED use LOCAL_APPS instead; can be removed with testrunner.py
TEST_APPS = ()

# also excludes any app starting with 'django.'
APPS_TO_EXCLUDE_FROM_TESTS = (
    'a5288',
    'captcha',
    'couchdbkit.ext.django',
    'corehq.apps.ivr',
    'corehq.messaging.smsbackends.mach',
    'corehq.messaging.smsbackends.http',
    'corehq.apps.settings',
    'corehq.messaging.smsbackends.megamobile',
    'corehq.messaging.smsbackends.yo',
    'corehq.messaging.smsbackends.smsgh',
    'corehq.messaging.smsbackends.push',
    'corehq.messaging.smsbackends.apposit',
    'crispy_forms',
    'django_extensions',
    'django_prbac',
    'django_otp',
    'django_otp.plugins.otp_static',
    'django_otp.plugins.otp_totp',
    'djcelery',
    'djtables',
    'gunicorn',
    'langcodes',
    'raven.contrib.django.raven_compat',
    'rosetta',
    'two_factor',
    'custom.apps.crs_reports',
    'custom.m4change',

    # submodules with tests that run on travis
    'dimagi.utils',
)

INSTALLED_APPS = DEFAULT_APPS + HQ_APPS + ENIKSHAY_APPS


# after login, django redirects to this URL
# rather than the default 'accounts/profile'
LOGIN_REDIRECT_URL = 'homepage'


REPORT_CACHE = 'default'  # or e.g. 'redis'

# When set to False, HQ will not cache any reports using is_cacheable
CACHE_REPORTS = True

####### Domain settings  #######

DOMAIN_MAX_REGISTRATION_REQUESTS_PER_DAY = 99
DOMAIN_SELECT_URL = "/domain/select/"

# This is not used by anything in CommCare HQ, leaving it here in case anything
# in Django unexpectedly breaks without it.
LOGIN_URL = "/accounts/login/"
# If a user tries to access domain admin pages but isn't a domain
# administrator, here's where he/she is redirected
DOMAIN_NOT_ADMIN_REDIRECT_PAGE_NAME = "homepage"

PAGES_NOT_RESTRICTED_FOR_DIMAGI = (
    '/a/%(domain)s/settings/project/internal_subscription_management/',
    '/a/%(domain)s/settings/project/internal/info/',
    '/a/%(domain)s/settings/project/internal/calculations/',
    '/a/%(domain)s/settings/project/flags/'
)

####### Release Manager App settings  #######
RELEASE_FILE_PATH = os.path.join("data", "builds")

## soil heartbead config ##
SOIL_HEARTBEAT_CACHE_KEY = "django-soil-heartbeat"


####### Shared/Global/UI Settings #######

# restyle some templates
BASE_TEMPLATE = "style/base.html"
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
PROBONO_SUPPORT_EMAIL = 'pro-bono@dimagi.com'
CCHQ_BUG_REPORT_EMAIL = 'commcarehq-bug-reports@dimagi.com'
ACCOUNTS_EMAIL = 'accounts@dimagi.com'
DATA_EMAIL = 'datatree@dimagi.com'
SUBSCRIPTION_CHANGE_EMAIL = 'accounts+subchange@dimagi.com'
INTERNAL_SUBSCRIPTION_CHANGE_EMAIL = 'accounts+subchange+internal@dimagi.com'
BILLING_EMAIL = 'billing-comm@dimagi.com'
INVOICING_CONTACT_EMAIL = 'billing-support@dimagi.com'
MASTER_LIST_EMAIL = 'master-list@dimagi.com'
REPORT_BUILDER_ADD_ON_EMAIL = 'sales' + '@' + 'dimagi.com'
EULA_CHANGE_EMAIL = 'eula-notifications@dimagi.com'
CONTACT_EMAIL = 'info@dimagi.com'
BOOKKEEPER_CONTACT_EMAILS = []
SOFT_ASSERT_EMAIL = 'commcarehq-ops+soft_asserts@dimagi.com'
EMAIL_SUBJECT_PREFIX = '[commcarehq] '

SERVER_ENVIRONMENT = 'localdev'
BASE_ADDRESS = 'localhost:8000'
J2ME_ADDRESS = ''

# Set this if touchforms can't access HQ via the public URL e.g. if using a self signed cert
# Should include the protocol.
# If this is None, get_url_base() will be used
CLOUDCARE_BASE_URL = None

PAGINATOR_OBJECTS_PER_PAGE = 15
PAGINATOR_MAX_PAGE_LINKS = 5

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
        "corehq.apps.app_manager.fixtures.report_fixture_generator",
        "corehq.apps.calendar_fixture.fixture_provider.calendar_fixture_generator",
        # custom
        "custom.bihar.reports.indicators.fixtures.generator",
        "custom.m4change.fixtures.report_fixtures.generator",
        "custom.m4change.fixtures.location_fixtures.generator",

    ],
    # fixtures that must be sent along with the phones cases
    'case': [
        "corehq.apps.locations.fixtures.location_fixture_generator",
        "corehq.apps.locations.fixtures.flat_location_fixture_generator",
    ]
}

### Shared drive settings ###
# Also see section after localsettings import
SHARED_DRIVE_ROOT = None
# names of directories within SHARED_DRIVE_ROOT
RESTORE_PAYLOAD_DIR_NAME = None
SHARED_TEMP_DIR_NAME = None
SHARED_BLOB_DIR_NAME = 'blobdb'

## django-transfer settings
# These settings must match the apache / nginx config
TRANSFER_SERVER = None  # 'apache' or 'nginx'
# name of the directory within SHARED_DRIVE_ROOT
TRANSFER_FILE_DIR_NAME = None

GET_URL_BASE = 'dimagi.utils.web.get_url_base'

# celery
BROKER_URL = 'django://'  # default django db based

CELERY_ANNOTATIONS = {
    '*': {
        'on_failure': helper.celery_failure_handler,
        'trail': False,
    }
}

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


# This is the celery queue to use for sending repeat records.
# It's set to the main queue here and can be overridden to put it
# on its own queue.
CELERY_REPEAT_RECORD_QUEUE = CELERY_MAIN_QUEUE

# Will cause a celery task to raise a SoftTimeLimitExceeded exception if
# time limit is exceeded.
CELERYD_TASK_SOFT_TIME_LIMIT = 86400 * 2  # 2 days in seconds

# websockets config
WEBSOCKET_URL = '/ws/'
WS4REDIS_PREFIX = 'ws'
WSGI_APPLICATION = 'ws4redis.django_runserver.application'
WS4REDIS_ALLOWED_CHANNELS = helper.get_allowed_websocket_channels


TEST_RUNNER = 'testrunner.TwoStageTestRunner'
# this is what gets appended to @domain after your accounts
HQ_ACCOUNT_ROOT = "commcarehq.org"

XFORMS_PLAYER_URL = "http://localhost:4444/"  # touchform's setting
FORMPLAYER_URL = 'http://localhost:8080'

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
REMINDERS_QUEUE_ENQUEUING_TIMEOUT = 180

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

# Reminders rate limiting settings. A single project will only be allowed to
# fire REMINDERS_RATE_LIMIT_COUNT reminders every REMINDERS_RATE_LIMIT_PERIOD
# seconds.
REMINDERS_RATE_LIMIT_COUNT = 30
REMINDERS_RATE_LIMIT_PERIOD = 60


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
    'corehq.apps.hqadmin',
    'corehq.apps.accounting',
    'tastypie',
]

# Don't use google analytics unless overridden in localsettings
ANALYTICS_IDS = {
    'GOOGLE_ANALYTICS_API_ID': '',
    'KISSMETRICS_KEY': '',
    'HUBSPOT_API_KEY': '',
    'HUBSPOT_API_ID': '',
}

ANALYTICS_CONFIG = {
    "HQ_INSTANCE": '',  # e.g. "www" or "staging"
}

MAPBOX_ACCESS_TOKEN = 'pk.eyJ1IjoiZGltYWdpIiwiYSI6ImpZWWQ4dkUifQ.3FNy5rVvLolWLycXPxKVEA'

OPEN_EXCHANGE_RATES_API_ID = ''

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
LOCAL_REPEATERS = ()

# Prelogin site
ENABLE_PRELOGIN_SITE = False
PRELOGIN_APPS = (
    'corehq.apps.prelogin',
)

# our production logstash aggregation
LOGSTASH_DEVICELOG_PORT = 10777
LOGSTASH_AUDITCARE_PORT = 10999
LOGSTASH_HOST = 'localhost'

# on both a single instance or distributed setup this should assume localhost
ELASTICSEARCH_HOST = 'localhost'
ELASTICSEARCH_PORT = 9200
ELASTICSEARCH_VERSION = 1.7

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

PREVIEWER_RE = '^$'

MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'

DIGEST_LOGIN_FACTORY = 'django_digest.NoEmailLoginFactory'

# Django Compressor
COMPRESS_PRECOMPILERS = (
    ('text/less', 'corehq.apps.style.precompilers.LessFilter'),
)
COMPRESS_ENABLED = True
COMPRESS_JS_COMPRESSOR = 'corehq.apps.style.uglify.JsUglifySourcemapCompressor'
# use 'compressor.js.JsCompressor' for faster local compressing (will get rid of source maps)
COMPRESS_CSS_FILTERS = ['compressor.filters.css_default.CssAbsoluteFilter',
'compressor.filters.cssmin.rCSSMinFilter']

LESS_B3_PATHS = {
    'variables': '../../../style/less/_hq/includes/variables',
    'mixins': '../../../style/less/_hq/includes/mixins',
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

SQL_REPORTING_DATABASE_URL = None
UCR_DATABASE_URL = None

# Override this in localsettings to specify custom reporting databases
CUSTOM_DATABASES = {}

PL_PROXY_CLUSTER_NAME = 'commcarehq'

USE_PARTITIONED_DATABASE = False

# number of days since last access after which a saved export is considered unused
SAVED_EXPORT_ACCESS_CUTOFF = 35

# override for production
DEFAULT_PROTOCOL = 'http'

# Dropbox
DROPBOX_KEY = ''
DROPBOX_SECRET = ''
DROPBOX_APP_NAME = ''

# Amazon S3
S3_ACCESS_KEY = None
S3_SECRET_KEY = None

# Supervisor RPC
SUPERVISOR_RPC_ENABLED = False
SUBSCRIPTION_USERNAME = None
SUBSCRIPTION_PASSWORD = None

ENVIRONMENT_HOSTS = {
    'pillowtop': ['localhost']
}

DATADOG_API_KEY = None
DATADOG_APP_KEY = None

# Override with the PEM export of an RSA private key, for use with any
# encryption or signing workflows.
HQ_PRIVATE_KEY = None

# Settings for Zipline integration
ZIPLINE_API_URL = ''
ZIPLINE_API_USER = ''
ZIPLINE_API_PASSWORD = ''

KAFKA_URL = 'localhost:9092'

MOBILE_INTEGRATION_TEST_TOKEN = None

OVERRIDE_UCR_BACKEND = None

ENTERPRISE_MODE = False

CUSTOM_LANDING_PAGE = False

TABLEAU_URL_ROOT = "https://icds.commcarehq.org/"

ONBOARDING_DOMAIN_TEST_DATE = ()

HQ_INSTANCE = 'development'

try:
    # try to see if there's an environmental variable set for local_settings
    custom_settings = os.environ.get('CUSTOMSETTINGS', None)
    if custom_settings:
        if custom_settings == 'demo':
            from settings_demo import *
        else:
            custom_settings_module = importlib.import_module(custom_settings)
            try:
                attrlist = custom_settings_module.__all__
            except AttributeError:
                attrlist = dir(custom_settings_module)
            for attr in attrlist:
                globals()[attr] = getattr(custom_settings_module, attr)
    else:
        from localsettings import *
except ImportError as error:
    if error.message != 'No module named localsettings':
        raise error
    # fallback in case nothing else is found - used for readthedocs
    from dev_settings import *

_location = lambda x: os.path.join(FILEPATH, x)

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            _location('corehq/apps/domain/templates/login_and_password'),
        ],
        'OPTIONS': {
            'context_processors': [
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.core.context_processors.request',
                'django.template.context_processors.debug',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',

                'corehq.util.context_processors.base_template',
                'corehq.util.context_processors.current_url_name',
                'corehq.util.context_processors.domain',
                'corehq.util.context_processors.enterprise_mode',
                'corehq.util.context_processors.js_api_keys',
                'corehq.util.context_processors.websockets_override',
            ],
            'debug': DEBUG,
            'loaders': [
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
                'django.template.loaders.eggs.Loader',
            ],
        },
    },
]

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
        'couch-request-formatter': {
            'format': '%(asctime)s [%(username)s:%(domain)s] %(hq_url)s %(method)s %(status_code)s %(content_length)s %(path)s %(duration)s'
        },
        'datadog': {
            'format': '%(metric)s %(created)s %(value)s metric_type=%(metric_type)s %(message)s'
        },
        'ucr_timing': {
            'format': '%(asctime)s\t%(domain)s\t%(report_config_id)s\t%(filter_values)s\t%(control_duration)s\t%(candidate_duration)s'
        },
        'ucr_diff': {
            'format': '%(asctime)s\t%(domain)s\t%(report_config_id)s\t%(filter_values)s\t%(control)s\t%(diff)s'
        },
        'ucr_exception': {
            'format': '%(asctime)s\t%(domain)s\t%(report_config_id)s\t%(filter_values)s\t%(candidate)s'
        },
    },
    'filters': {
        'hqcontext': {
            '()': 'corehq.util.log.HQRequestFilter',
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
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'verbose',
            'filename': DJANGO_LOG_FILE,
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 20  # Backup 200 MB of logs
        },
        'couch-request-handler': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'couch-request-formatter',
            'filters': ['hqcontext'],
            'filename': COUCH_LOG_FILE,
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 20  # Backup 200 MB of logs
        },
        'accountinglog': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'verbose',
            'filename': ACCOUNTING_LOG_FILE,
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 20  # Backup 200 MB of logs
        },
        'analyticslog': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'verbose',
            'filename': ANALYTICS_LOG_FILE,
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 20  # Backup 200 MB of logs
        },
        'datadog': {
            'level': 'INFO',
            'class': 'cloghandler.ConcurrentRotatingFileHandler',
            'formatter': 'datadog',
            'filename': DATADOG_LOG_FILE,
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 20  # Backup 200 MB of logs
        },
        'ucr_diff': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'ucr_diff',
            'filename': UCR_DIFF_FILE,
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 20  # Backup 200 MB of logs
        },
        'ucr_exception': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'ucr_exception',
            'filename': UCR_EXCEPTION_FILE,
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 20  # Backup 200 MB of logs
        },
        'ucr_timing': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'ucr_timing',
            'filename': UCR_TIMING_FILE,
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 20  # Backup 200 MB of logs
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'corehq.util.log.HqAdminEmailHandler',
        },
        'notify_exception': {
            'level': 'ERROR',
            'class': 'corehq.util.log.NotifyExceptionEmailer',
        },
        'null': {
            'class': 'logging.NullHandler',
        },
        'nikshay_datamigration': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'verbose',
            'filename': NIKSHAY_DATAMIGRATION,
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 20  # Backup 200 MB of logs
        },
    },
    'loggers': {
        '': {
            'handlers': ['console', 'file'],
            'propagate': True,
            'level': 'INFO',
        },
        'couchdbkit.request': {
            'handlers': ['couch-request-handler'],
            'level': 'DEBUG',
            'propagate': False,
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
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True
        },
        'pillowtop': {
            'handlers': ['pillowtop'],
            'level': 'ERROR',
            'propagate': False,
        },
        'smsbillables': {
            'handlers': ['file', 'console', 'mail_admins'],
            'level': 'INFO',
            'propagate': False,
        },
        'accounting': {
            'handlers': ['accountinglog', 'console', 'mail_admins'],
            'level': 'INFO',
            'propagate': False,
        },
        'analytics': {
            'handlers': ['analyticslog'],
            'level': 'DEBUG',
            'propagate': False
        },
        'elasticsearch': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': True,
        },
        'datadog-metrics': {
            'handlers': ['datadog'],
            'level': 'INFO',
            'propagate': False,
        },
        'ucr_timing': {
            'handlers': ['ucr_timing'],
            'level': 'INFO',
            'propagate': True,
        },
        'ucr_diff': {
            'handlers': ['ucr_diff'],
            'level': 'INFO',
            'propagate': True,
        },
        'ucr_exception': {
            'handlers': ['ucr_exception'],
            'level': 'INFO',
            'propagate': True,
        },
        'boto3': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': True
        },
        'botocore': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': True
        },
        'nikshay_datamigration': {
            'handlers': ['nikshay_datamigration', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    }
}

LOGGING['handlers'].update(LOCAL_LOGGING_HANDLERS)
LOGGING['loggers'].update(LOCAL_LOGGING_LOGGERS)

fix_logger_obfuscation_ = globals().get("FIX_LOGGER_ERROR_OBFUSCATION")
helper.fix_logger_obfuscation(fix_logger_obfuscation_, LOGGING)

if DEBUG:
    INSTALLED_APPS = INSTALLED_APPS + ('corehq.apps.mocha',)
    import warnings
    warnings.simplefilter('default')
    os.environ['PYTHONWARNINGS'] = 'd'  # Show DeprecationWarning
else:
    TEMPLATES[0]['OPTIONS']['loaders'] = [[
        'django.template.loaders.cached.Loader',
        TEMPLATES[0]['OPTIONS']['loaders']
    ]]

if helper.is_testing():
    helper.assign_test_db_names(DATABASES)

### Reporting database - use same DB as main database

db_settings = DATABASES["default"].copy()
db_settings['PORT'] = db_settings.get('PORT', '5432')
options = db_settings.get('OPTIONS')
db_settings['OPTIONS'] = '?{}'.format(urlencode(options)) if options else ''

if not SQL_REPORTING_DATABASE_URL or UNIT_TESTING:
    SQL_REPORTING_DATABASE_URL = "postgresql+psycopg2://{USER}:{PASSWORD}@{HOST}:{PORT}/{NAME}{OPTIONS}".format(
        **db_settings
    )

if not UCR_DATABASE_URL or UNIT_TESTING:
    # by default just use the reporting DB for UCRs
    UCR_DATABASE_URL = SQL_REPORTING_DATABASE_URL

if USE_PARTITIONED_DATABASE:
    DATABASE_ROUTERS = ['corehq.sql_db.routers.PartitionRouter']
else:
    DATABASE_ROUTERS = ['corehq.sql_db.routers.MonolithRouter']

MVP_INDICATOR_DB = 'mvp-indicators'

INDICATOR_CONFIG = {
    "mvp-sauri": ['mvp_indicators'],
    "mvp-potou": ['mvp_indicators'],
}

COMPRESS_URL = STATIC_CDN + STATIC_URL

####### Couch Forms & Couch DB Kit Settings #######
COUCH_DATABASE_NAME = helper.get_db_name(COUCH_DATABASE_NAME, UNIT_TESTING)
_dynamic_db_settings = helper.get_dynamic_db_settings(
    COUCH_SERVER_ROOT,
    COUCH_USERNAME,
    COUCH_PASSWORD,
    COUCH_DATABASE_NAME,
    use_https=COUCH_HTTPS,
)

# create local server and database configs
COUCH_DATABASE = _dynamic_db_settings["COUCH_DATABASE"]

NEW_USERS_GROUPS_DB = 'users'
USERS_GROUPS_DB = NEW_USERS_GROUPS_DB

NEW_FIXTURES_DB = 'fixtures'
FIXTURES_DB = NEW_FIXTURES_DB

NEW_DOMAINS_DB = 'domains'
DOMAINS_DB = NEW_DOMAINS_DB

NEW_APPS_DB = 'apps'
APPS_DB = NEW_APPS_DB

SYNCLOGS_DB = 'synclogs'


COUCHDB_APPS = [
    'api',
    'appstore',
    'builds',
    'case',
    'casegroups',
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
    'custom_data_fields',
    'hqadmin',
    'ext',
    'facilities',
    'fluff_filter',
    'hqcase',
    'hqmedia',
    'hope',
    'case_importer',
    'indicators',
    'locations',
    'mobile_auth',
    'pillowtop',
    'pillow_retry',
    'products',
    'programs',
    'reminders',
    'reports',
    'sms',
    'smsforms',
    'telerivet',
    'toggle',
    'translations',
    'utils',  # dimagi-utils
    'formplayer',
    'phonelog',
    'registration',
    'wisepill',
    'fri',
    'crs_reports',
    'grapevine',
    'uth',
    'openclinica',

    # custom reports
    'gsid',
    'hsph',
    'mvp',
    ('mvp_docs', MVP_INDICATOR_DB),
    'pact',
    'accounting',
    'succeed',
    'ilsgateway',
    'ewsghana',
    ('auditcare', 'auditcare'),
    ('performance_sms', 'meta'),
    ('repeaters', 'receiverwrapper'),
    ('userreports', 'meta'),
    ('custom_data_fields', 'meta'),
    # needed to make couchdbkit happy
    ('fluff', 'fluff-bihar'),
    ('bihar', 'fluff-bihar'),
    ('opm', 'fluff-opm'),
    ('fluff', 'fluff-opm'),
    ('mc', 'fluff-mc'),
    ('m4change', 'm4change'),
    ('export', 'meta'),
    ('callcenter', 'meta'),

    # users and groups
    ('groups', USERS_GROUPS_DB),
    ('users', USERS_GROUPS_DB),

    # fixtures
    ('fixtures', FIXTURES_DB),

    # domains
    ('domain', DOMAINS_DB),

    # sync logs
    ('phone', SYNCLOGS_DB),

    # applications
    ('app_manager', APPS_DB),
]

COUCHDB_APPS += LOCAL_COUCHDB_APPS

COUCH_SETTINGS_HELPER = helper.CouchSettingsHelper(
    COUCH_DATABASE,
    COUCHDB_APPS,
    [NEW_USERS_GROUPS_DB, NEW_FIXTURES_DB, NEW_DOMAINS_DB, NEW_APPS_DB],
)
COUCHDB_DATABASES = COUCH_SETTINGS_HELPER.make_couchdb_tuples()
EXTRA_COUCHDB_DATABASES = COUCH_SETTINGS_HELPER.get_extra_couchdbs()

# note: the only reason LOCAL_APPS come before INSTALLED_APPS is because of
# a weird travis issue with kafka. if for any reason this order causes problems
# it can be reverted whenever that's figured out.
# https://github.com/dimagi/commcare-hq/pull/10034#issuecomment-174868270
INSTALLED_APPS = LOCAL_APPS + INSTALLED_APPS

if ENABLE_PRELOGIN_SITE:
    INSTALLED_APPS += PRELOGIN_APPS

seen = set()
INSTALLED_APPS = [x for x in INSTALLED_APPS if x not in seen and not seen.add(x)]

MIDDLEWARE_CLASSES += LOCAL_MIDDLEWARE_CLASSES

### Shared drive settings ###
SHARED_DRIVE_CONF = helper.SharedDriveConfiguration(
    SHARED_DRIVE_ROOT,
    RESTORE_PAYLOAD_DIR_NAME,
    TRANSFER_FILE_DIR_NAME,
    SHARED_TEMP_DIR_NAME,
    SHARED_BLOB_DIR_NAME
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
# EMAIL_USE_TLS is set above
# so it can be overridden in localsettings (e.g. in a dev environment)

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

CUSTOM_SMS_HANDLERS = [
    'custom.ilsgateway.tanzania.handler.handle',
    'custom.ewsghana.handler.handle',
]

SMS_HANDLERS = [
    'corehq.apps.sms.handlers.forwarding.forwarding_handler',
    'corehq.apps.commtrack.sms.handle',
    'corehq.apps.sms.handlers.keyword.sms_keyword_handler',
    'corehq.apps.sms.handlers.form_session.form_session_handler',
    'corehq.apps.sms.handlers.fallback.fallback_handler',
]


SMS_LOADED_SQL_BACKENDS = [
    'corehq.messaging.smsbackends.apposit.models.SQLAppositBackend',
    'corehq.messaging.smsbackends.grapevine.models.SQLGrapevineBackend',
    'corehq.messaging.smsbackends.http.models.SQLHttpBackend',
    'corehq.messaging.smsbackends.icds_nic.models.SQLICDSBackend',
    'corehq.messaging.smsbackends.mach.models.SQLMachBackend',
    'corehq.messaging.smsbackends.megamobile.models.SQLMegamobileBackend',
    'corehq.messaging.smsbackends.push.models.PushBackend',
    'corehq.messaging.smsbackends.sislog.models.SQLSislogBackend',
    'corehq.messaging.smsbackends.smsgh.models.SQLSMSGHBackend',
    'corehq.messaging.smsbackends.telerivet.models.SQLTelerivetBackend',
    'corehq.messaging.smsbackends.test.models.SQLTestSMSBackend',
    'corehq.messaging.smsbackends.tropo.models.SQLTropoBackend',
    'corehq.messaging.smsbackends.twilio.models.SQLTwilioBackend',
    'corehq.messaging.smsbackends.unicel.models.SQLUnicelBackend',
    'corehq.messaging.smsbackends.yo.models.SQLYoBackend',
]

IVR_LOADED_SQL_BACKENDS = [
    'corehq.messaging.ivrbackends.kookoo.models.SQLKooKooBackend',
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

CASE_WRAPPER = 'corehq.apps.hqcase.utils.get_case_wrapper'

PILLOWTOPS = {
    'core': [
        {
            'name': 'CaseToElasticsearchPillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.pillows.case.get_case_to_elasticsearch_pillow',
        },
        {
            'name': 'XFormToElasticsearchPillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.pillows.xform.get_xform_to_elasticsearch_pillow',
        },
        {
            'name': 'UserPillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.pillows.user.get_user_pillow',
        },
        {
            'name': 'ApplicationToElasticsearchPillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.pillows.application.get_app_to_elasticsearch_pillow',
        },
        {
            'name': 'GroupPillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.pillows.group.get_group_pillow',
        },
        {
            'name': 'GroupToUserPillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.pillows.groups_to_user.get_group_to_user_pillow',
        },
        {
            'name': 'SqlSMSPillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.pillows.sms.get_sql_sms_pillow',
        },
        {
            'name': 'UserGroupsDbKafkaPillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.apps.change_feed.pillow.get_user_groups_db_kafka_pillow',
        },
        {
            'name': 'KafkaDomainPillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.pillows.domain.get_domain_kafka_to_elasticsearch_pillow',
        },
        {
            'name': 'AppFormSubmissionTrackerPillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.pillows.app_submission_tracker.get_app_form_submission_tracker_pillow',
        },
    ],
    'core_ext': [
        {
            'name': 'AppDbChangeFeedPillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.apps.change_feed.pillow.get_application_db_kafka_pillow',
        },
        {
            'name': 'DefaultChangeFeedPillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.apps.change_feed.pillow.get_default_couch_db_change_feed_pillow',
        },
        {
            'name': 'DomainDbKafkaPillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.apps.change_feed.pillow.get_domain_db_kafka_pillow',
        },
        {
            'name': 'kafka-ucr-main',
            'class': 'corehq.apps.userreports.pillow.ConfigurableReportKafkaPillow',
            'instance': 'corehq.apps.userreports.pillow.get_kafka_ucr_pillow',
        },
        {
            'name': 'kafka-ucr-static',
            'class': 'corehq.apps.userreports.pillow.ConfigurableReportKafkaPillow',
            'instance': 'corehq.apps.userreports.pillow.get_kafka_ucr_static_pillow',
        },
        {
            'name': 'ReportCaseToElasticsearchPillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.pillows.reportcase.get_report_case_to_elasticsearch_pillow',
        },
        {
            'name': 'ReportXFormToElasticsearchPillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.pillows.reportxform.get_report_xform_to_elasticsearch_pillow',
        },
        {
            'name': 'UnknownUsersPillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.pillows.user.get_unknown_users_pillow',
        },
    ],
    'cache': [
        {
            'name': 'CacheInvalidatePillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.pillows.cacheinvalidate.get_main_cache_invalidation_pillow',
        },
        {
            'name': 'UserCacheInvalidatePillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.pillows.cacheinvalidate.get_user_groups_cache_invalidation_pillow',
        },
    ],
    'fluff': [
        'custom.bihar.models.CareBiharFluffPillow',
        'custom.opm.models.OpmUserFluffPillow',
        'custom.m4change.models.AncHmisCaseFluffPillow',
        'custom.m4change.models.LdHmisCaseFluffPillow',
        'custom.m4change.models.ImmunizationHmisCaseFluffPillow',
        'custom.m4change.models.ProjectIndicatorsCaseFluffPillow',
        'custom.m4change.models.McctMonthlyAggregateFormFluffPillow',
        'custom.m4change.models.AllHmisCaseFluffPillow',
        'custom.intrahealth.models.CouvertureFluffPillow',
        'custom.intrahealth.models.TauxDeSatisfactionFluffPillow',
        'custom.intrahealth.models.IntraHealthFluffPillow',
        'custom.intrahealth.models.RecapPassageFluffPillow',
        'custom.intrahealth.models.TauxDeRuptureFluffPillow',
        'custom.intrahealth.models.LivraisonFluffPillow',
        'custom.intrahealth.models.RecouvrementFluffPillow',
        'custom.care_pathways.models.GeographyFluffPillow',
        'custom.care_pathways.models.FarmerRecordFluffPillow',
        'custom.world_vision.models.WorldVisionMotherFluffPillow',
        'custom.world_vision.models.WorldVisionChildFluffPillow',
        'custom.world_vision.models.WorldVisionHierarchyFluffPillow',
        'custom.succeed.models.UCLAPatientFluffPillow',
    ],
    'mvp_indicators': [
        {
            'name': 'MVPCaseIndicatorPillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'mvp_docs.pillows.get_mvp_case_indicator_pillow',
        },
        {
            'name': 'MVPFormIndicatorPillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'mvp_docs.pillows.get_mvp_form_indicator_pillow',
        },
    ],
    'experimental': [
        {
            'name': 'BlobDeletionPillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.blobs.pillow.get_main_blob_deletion_pillow',
        },
        {
            'name': 'ApplicationBlobDeletionPillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.blobs.pillow.get_application_blob_deletion_pillow',
        },
        {
            'name': 'CaseSearchToElasticsearchPillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.pillows.case_search.get_case_search_to_elasticsearch_pillow',
        },
        {
            'name': 'LedgerToElasticsearchPillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.pillows.ledger.get_ledger_to_elasticsearch_pillow',
        },
    ]
}

BASE_REPEATERS = (
    'corehq.apps.repeaters.models.FormRepeater',
    'corehq.apps.repeaters.models.CaseRepeater',
    'corehq.apps.repeaters.models.ShortFormRepeater',
    'corehq.apps.repeaters.models.AppStructureRepeater',
)

CUSTOM_REPEATERS = (
    'custom.enikshay.integrations.ninetyninedots.repeaters.NinetyNineDotsRegisterPatientRepeater',
    'custom.enikshay.integrations.ninetyninedots.repeaters.NinetyNineDotsUpdatePatientRepeater',
    'custom.enikshay.integrations.nikshay.repeaters.NikshayRegisterPatientRepeater'
)

REPEATERS = BASE_REPEATERS + LOCAL_REPEATERS + CUSTOM_REPEATERS


STATIC_UCR_REPORTS = [
    os.path.join('custom', '_legacy', 'mvp', 'ucr', 'reports', 'deidentified_va_report.json'),
    os.path.join('custom', 'abt', 'reports', 'incident_report.json'),
    os.path.join('custom', 'abt', 'reports', 'sms_indicator_report.json'),
    os.path.join('custom', 'abt', 'reports', 'spray_progress_country.json'),
    os.path.join('custom', 'abt', 'reports', 'spray_progress_level_1.json'),
    os.path.join('custom', 'abt', 'reports', 'spray_progress_level_2.json'),
    os.path.join('custom', 'abt', 'reports', 'spray_progress_level_3.json'),
    os.path.join('custom', 'abt', 'reports', 'spray_progress_level_4.json'),
    os.path.join('custom', 'abt', 'reports', 'supervisory_report.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'asr_2_3_person_cases.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'asr_2_household_cases.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'asr_2_lactating.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'asr_2_pregnancies.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'asr_4_6_infrastructure.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'it_individual_issues.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'it_issues_block.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'it_issues_by_ticket_level.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'it_issues_by_type.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'it_issues_district.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'it_issues_state.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'mpr_10a_person_cases.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'mpr_10b_person_cases.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'mpr_11_visitor_book_forms.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'mpr_1_person_cases.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'mpr_2a_3_child_delivery_forms.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'mpr_2a_person_cases.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'mpr_2bi_preg_delivery_death_list.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'mpr_2bii_child_death_list.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'mpr_2ci_child_birth_list.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'mpr_3i_person_cases.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'mpr_3ii_person_cases.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'mpr_4a_6_pse.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'mpr_4b_infra_forms.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'mpr_5_ccs_record_cases.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'mpr_5_child_health_cases.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'mpr_6ac_child_health_cases.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'mpr_6b_child_health_cases.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'mpr_7_growth_monitoring_forms.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'mpr_8_tasks_cases.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'mpr_9_vhnd_forms.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'list_pnc_delivery_complications.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'ls_above_6mo_nutrition.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'ls_awc_days_open.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'ls_awc_locations.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'ls_awc_mgmt_forms.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'ls_beneficiary_feedback.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'ls_born_last_30_days.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'ls_child_nutrition_status.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'ls_children_weighed.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'ls_comp_feeding.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'ls_ebf.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'ls_handwashing.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'ls_ifa_consumption.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'ls_immun_complete.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'ls_report_child_names.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'ls_report_child_nutrition_status.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'ls_report_lbw_pre_term.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'ls_report_pregnant_women_names.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'ls_thr_30_days.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'ls_thr_forms.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'ls_timely_home_visits.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'ls_ccs_record_cases.json'),

    os.path.join('custom', 'enikshay', 'ucr', 'reports', 'tb_notification_register.json'),
    os.path.join('custom', 'enikshay', 'ucr', 'reports', 'sputum_conversion.json'),
    os.path.join('custom', 'enikshay', 'ucr', 'reports', 'tb_hiv.json'),
    os.path.join('custom', 'enikshay', 'ucr', 'reports', 'lab_monthly_summary.json'),
    os.path.join('custom', 'enikshay', 'ucr', 'reports', 'tb_lab_register.json'),
    os.path.join('custom', 'enikshay', 'ucr', 'reports', 'new_patient_summary.json'),
    os.path.join('custom', 'enikshay', 'ucr', 'reports', 'mdr_suspects.json'),
    os.path.join('custom', 'enikshay', 'ucr', 'reports', 'patient_overview_mobile.json'),
    os.path.join('custom', 'enikshay', 'ucr', 'reports', 'patients_due_to_follow_up.json'),
    os.path.join('custom', 'enikshay', 'ucr', 'reports', 'treatment_outcome_mobile.json'),
    os.path.join('custom', 'enikshay', 'ucr', 'reports', 'case_finding_mobile.json')
]


STATIC_DATA_SOURCES = [
    os.path.join('custom', 'up_nrhm', 'data_sources', 'location_hierarchy.json'),
    os.path.join('custom', 'up_nrhm', 'data_sources', 'asha_facilitators.json'),
    os.path.join('custom', 'succeed', 'data_sources', 'submissions.json'),
    os.path.join('custom', 'succeed', 'data_sources', 'patient_task_list.json'),
    os.path.join('custom', 'apps', 'gsid', 'data_sources', 'patient_summary.json'),
    os.path.join('custom', 'abt', 'reports', 'data_sources', 'sms.json'),
    os.path.join('custom', 'abt', 'reports', 'data_sources', 'sms_case.json'),
    os.path.join('custom', 'abt', 'reports', 'data_sources', 'supervisory.json'),
    os.path.join('custom', '_legacy', 'mvp', 'ucr', 'reports', 'data_sources', 'va_datasource.json'),
    os.path.join('custom', 'reports', 'mc', 'data_sources', 'malaria_consortium.json'),
    os.path.join('custom', 'reports', 'mc', 'data_sources', 'weekly_forms.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'awc_locations.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'awc_mgt_forms.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'ccs_record_cases.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'ccs_record_cases_monthly.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'ccs_record_cases_monthly_tableau.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'child_cases_monthly.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'child_delivery_forms.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'child_health_cases.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'child_health_cases_monthly_tableau.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'daily_feeding_forms.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'gm_forms.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'home_visit_forms.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'household_cases.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'infrastructure_form.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'ls_home_visit_forms_filled.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'person_cases.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'tasks_cases.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'tech_issue_cases.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'thr_forms.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'usage_forms.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'vhnd_form.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'visitorbook_forms.json'),

    os.path.join('custom', 'enikshay', 'ucr', 'data_sources', 'episode.json'),
    os.path.join('custom', 'enikshay', 'ucr', 'data_sources', 'test.json'),

    os.path.join('custom', 'pnlppgi', 'resources', 'site_reporting_rates.json'),
    os.path.join('custom', 'pnlppgi', 'resources', 'malaria.json')
]

STATIC_DATA_SOURCE_PROVIDERS = [
    'corehq.apps.callcenter.data_source.call_center_data_source_configuration_provider'
]


for k, v in LOCAL_PILLOWTOPS.items():
    plist = PILLOWTOPS.get(k, [])
    plist.extend(v)
    PILLOWTOPS[k] = plist

COUCH_CACHE_BACKENDS = [
    'corehq.apps.cachehq.cachemodels.DomainGenerationCache',
    'corehq.apps.cachehq.cachemodels.UserGenerationCache',
    'corehq.apps.cachehq.cachemodels.GroupGenerationCache',
    'corehq.apps.cachehq.cachemodels.UserRoleGenerationCache',
    'corehq.apps.cachehq.cachemodels.ReportGenerationCache',
    'corehq.apps.cachehq.cachemodels.DefaultConsumptionGenerationCache',
    'corehq.apps.cachehq.cachemodels.InvitationGenerationCache',
    'corehq.apps.cachehq.cachemodels.UserReportsDataSourceCache',
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
    ('succeed_referenced_id', 'custom.succeed.expressions.succeed_referenced_id'),
    ('location_type_name', 'corehq.apps.locations.ucr_expressions.location_type_name'),
    ('location_parent_id', 'corehq.apps.locations.ucr_expressions.location_parent_id'),
    ('eqa_expression', 'custom.eqa.expressions.eqa_expression'),
    ('cqi_action_item', 'custom.eqa.expressions.cqi_action_item'),
    ('year_expression', 'custom.pnlppgi.expressions.year_expression'),
    ('week_expression', 'custom.pnlppgi.expressions.week_expression'),
    ('concatenate_strings', 'custom.enikshay.expressions.concatenate_strings_expression')
]

CUSTOM_UCR_EXPRESSION_LISTS = [
    ('mvp.ucr.reports.expressions.CUSTOM_UCR_EXPRESSIONS'),
    ('custom.icds_reports.ucr.expressions.CUSTOM_UCR_EXPRESSIONS'),
    ('custom.ucr_ext.expressions.CUSTOM_UCR_EXPRESSIONS'),
]

CUSTOM_MODULES = [
    'custom.apps.crs_reports',
    'custom.ilsgateway',
    'custom.ewsghana',
]

CUSTOM_DASHBOARD_PAGE_URL_NAMES = {
    'ews-ghana': 'dashboard_page',
    'ils-gateway': 'ils_dashboard_report'
}

REMOTE_APP_NAMESPACE = "%(domain)s.commcarehq.org"

# a DOMAIN_MODULE_CONFIG doc present in your couchdb can override individual
# items.
DOMAIN_MODULE_MAP = {
    'a5288-test': 'a5288',
    'a5288-study': 'a5288',
    'care-bihar': 'custom.bihar',
    'bihar': 'custom.bihar',
    'fri': 'custom.fri.reports',
    'fri-testing': 'custom.fri.reports',
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
    'mvp-tiby': 'mvp',
    'mvp-mbola': 'mvp',
    'mvp-koraro': 'mvp',
    'mvp-pampaida': 'mvp',
    'opm': 'custom.opm',
    'pact': 'pact',

    'ipm-senegal': 'custom.intrahealth',
    'icds-test': 'custom.icds_reports',
    'icds-cas': 'custom.icds_reports',
    'testing-ipm-senegal': 'custom.intrahealth',
    'up-nrhm': 'custom.up_nrhm',

    'enikshay-test': 'custom.enikshay',
    'enikshay': 'custom.enikshay',
    'enikshay-test-2': 'custom.enikshay',
    'enikshay-test-3': 'custom.enikshay',
    'enikshay-nikshay-migration-test': 'custom.enikshay',
    'enikshay-domain-copy-test': 'custom.enikshay',
    'enikshay-aks-audit': 'custom.enikshay',
    'np-migration-3': 'custom.enikshay',

    'crs-remind': 'custom.apps.crs_reports',

    'm4change': 'custom.m4change',
    'succeed': 'custom.succeed',
    'test-pathfinder': 'custom.m4change',
    'wvindia2': 'custom.world_vision',
    'pathways-india-mis': 'custom.care_pathways',
    'pathways-tanzania': 'custom.care_pathways',
    'care-macf-malawi': 'custom.care_pathways',
    'care-macf-bangladesh': 'custom.care_pathways',
    'care-macf-ghana': 'custom.care_pathways',
    'pnlppgi': 'custom.pnlppgi'
}

CASEXML_FORCE_DOMAIN_CHECK = True

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



if 'locmem' not in CACHES:
    CACHES['locmem'] = {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}
if 'dummy' not in CACHES:
    CACHES['dummy'] = {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}

try:
    from datadog import initialize
except ImportError:
    pass
else:
    initialize(DATADOG_API_KEY, DATADOG_APP_KEY)

REST_FRAMEWORK = {
    'DATETIME_FORMAT': '%Y-%m-%dT%H:%M:%S.%fZ'
}
