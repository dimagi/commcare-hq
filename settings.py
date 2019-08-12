#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import unicode_literals

import inspect
from collections import defaultdict
import importlib
import os
import six

from django.contrib import messages
import settingshelper as helper

DEBUG = True
LESS_DEBUG = DEBUG

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
DISABLE_RANDOM_TOGGLES = UNIT_TESTING

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

# These templates are put on the server during deploy by fabric
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

STATICFILES_DIRS = [
    BOWER_COMPONENTS,
]

# bleh, why did this submodule have to be removed?
# deploy fails if this item is present and the path does not exist
_formdesigner_path = os.path.join(FILEPATH, 'submodules', 'formdesigner')
if os.path.exists(_formdesigner_path):
    STATICFILES_DIRS += (('formdesigner', _formdesigner_path),)
del _formdesigner_path

LOG_HOME = FILEPATH
COUCH_LOG_FILE = "%s/%s" % (FILEPATH, "commcarehq.couch.log")
DJANGO_LOG_FILE = "%s/%s" % (FILEPATH, "commcarehq.django.log")
ACCOUNTING_LOG_FILE = "%s/%s" % (FILEPATH, "commcarehq.accounting.log")
ANALYTICS_LOG_FILE = "%s/%s" % (FILEPATH, "commcarehq.analytics.log")
FORMPLAYER_TIMING_FILE = "%s/%s" % (FILEPATH, "formplayer.timing.log")
FORMPLAYER_DIFF_FILE = "%s/%s" % (FILEPATH, "formplayer.diff.log")
SOFT_ASSERTS_LOG_FILE = "%s/%s" % (FILEPATH, "soft_asserts.log")
MAIN_COUCH_SQL_DATAMIGRATION = "%s/%s" % (FILEPATH, "main_couch_sql_datamigration.log")

LOCAL_LOGGING_HANDLERS = {}
LOCAL_LOGGING_LOGGERS = {}

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/static/admin/'

# Make this unique, and don't share it with anybody - put into localsettings.py
SECRET_KEY = 'you should really change this'

MIDDLEWARE = [
    'corehq.middleware.NoCacheMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.common.BrokenLinkEmailsMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'django_user_agents.middleware.UserAgentMiddleware',
    'corehq.middleware.OpenRosaMiddleware',
    'corehq.util.global_request.middleware.GlobalRequestMiddleware',
    'corehq.apps.users.middleware.UsersMiddleware',
    'corehq.middleware.SentryContextMiddleware',
    'corehq.apps.domain.middleware.DomainMigrationMiddleware',
    'corehq.middleware.TimeoutMiddleware',
    'corehq.middleware.LogLongRequestMiddleware',
    'corehq.apps.domain.middleware.CCHQPRBACMiddleware',
    'corehq.apps.domain.middleware.DomainHistoryMiddleware',
    'corehq.apps.domain.project_access.middleware.ProjectAccessMiddleware',
    'casexml.apps.phone.middleware.SyncTokenMiddleware',
    'auditcare.middleware.AuditMiddleware',
    'no_exceptions.middleware.NoExceptionsMiddleware',
    'corehq.apps.locations.middleware.LocationAccessMiddleware',
]

SESSION_ENGINE = "django.contrib.sessions.backends.cache"

# time in minutes before forced logout due to inactivity
INACTIVITY_TIMEOUT = 60 * 24 * 14
SECURE_TIMEOUT = 30
ENABLE_DRACONIAN_SECURITY_FEATURES = False

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'corehq.apps.domain.auth.ApiKeyFallbackBackend',
]

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
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.humanize',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.staticfiles',
    'django_celery_results',
    'django_prbac',
    'djangular',
    'captcha',
    'couchdbkit.ext.django',
    'crispy_forms',
    'gunicorn',
    'compressor',
    'tastypie',
    'django_otp',
    'django_otp.plugins.otp_static',
    'django_otp.plugins.otp_totp',
    'two_factor',
    'ws4redis',
    'statici18n',
    'raven.contrib.django.raven_compat',
    'django_user_agents',
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
    'casexml.apps.case',
    'corehq.apps.casegroups',
    'corehq.apps.case_migrations',
    'casexml.apps.phone',
    'casexml.apps.stock',
    'corehq.apps.cleanup',
    'corehq.apps.cloudcare',
    'corehq.apps.couch_sql_migration',
    'corehq.apps.smsbillables',
    'corehq.apps.accounting',
    'corehq.apps.appstore',
    'corehq.apps.data_analytics',
    'corehq.apps.data_pipeline_audit',
    'corehq.apps.domain',
    'corehq.apps.domainsync',
    'corehq.apps.domain_migration_flags',
    'corehq.apps.dump_reload',
    'corehq.apps.hqadmin',
    'corehq.apps.hqcase',
    'corehq.apps.hqwebapp',
    'corehq.apps.hqmedia',
    'corehq.apps.integration',
    'corehq.apps.linked_domain',
    'corehq.apps.locations',
    'corehq.apps.products',
    'corehq.apps.programs',
    'corehq.apps.commtrack',
    'corehq.apps.consumption',
    'corehq.apps.tzmigration',
    'corehq.celery_monitoring.app_config.CeleryMonitoringAppConfig',
    'corehq.form_processor.app_config.FormProcessorAppConfig',
    'corehq.sql_db',
    'corehq.sql_accessors',
    'corehq.sql_proxy_accessors',
    'couchforms',
    'couchexport',
    'dimagi.utils',
    'langcodes',
    'corehq.apps.data_dictionary',
    'corehq.apps.analytics',
    'corehq.apps.callcenter',
    'corehq.apps.change_feed',
    'corehq.apps.custom_data_fields',
    'corehq.apps.receiverwrapper',
    'corehq.apps.app_manager',
    'corehq.apps.es',
    'corehq.apps.fixtures',
    'corehq.apps.calendar_fixture',
    'corehq.apps.case_importer',
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
    'corehq.messaging',
    'corehq.messaging.scheduling',
    'corehq.messaging.scheduling.scheduling_partitioned',
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
    'corehq.messaging.smsbackends.starfish',
    'corehq.messaging.smsbackends.apposit',
    'corehq.messaging.smsbackends.test',
    'corehq.apps.registration',
    'corehq.messaging.smsbackends.unicel',
    'corehq.messaging.smsbackends.icds_nic',
    'corehq.messaging.smsbackends.vertex',
    'corehq.messaging.smsbackends.start_enterprise',
    'corehq.messaging.smsbackends.ivory_coast_mtn',
    'corehq.messaging.smsbackends.karix',
    'corehq.messaging.smsbackends.airtel_tcl',
    'corehq.apps.reports.app_config.ReportsModule',
    'corehq.apps.reports_core',
    'corehq.apps.saved_reports',
    'corehq.apps.userreports',
    'corehq.apps.aggregate_ucrs',
    'corehq.apps.data_interfaces',
    'corehq.apps.export',
    'corehq.apps.builds',
    'corehq.apps.api',
    'corehq.apps.notifications',
    'corehq.apps.cachehq',
    'corehq.apps.toggle_ui',
    'corehq.apps.hqpillow_retry',
    'corehq.couchapps',
    'corehq.preindex',
    'corehq.tabs',
    'custom.apps.wisepill',
    'custom.openclinica',
    'fluff',
    'fluff.fluff_filter',
    'soil',
    'toggle',
    'phonelog',
    'pillowtop',
    'pillow_retry',
    'corehq.apps.styleguide',
    'corehq.messaging.smsbackends.grapevine',
    'corehq.apps.dashboard',
    'corehq.motech',
    'corehq.motech.dhis2',
    'corehq.motech.openmrs',
    'corehq.motech.repeaters',
    'corehq.util',
    'dimagi.ext',
    'corehq.doctypemigrations',
    'corehq.blobs',
    'corehq.warehouse',
    'corehq.apps.case_search',
    'corehq.apps.zapier.apps.ZapierConfig',
    'corehq.apps.translations',

    # custom reports
    'hsph',
    'pact',

    'custom.reports.mc',
    'custom.apps.crs_reports',
    'custom.ilsgateway',
    'custom.zipline',
    'custom.ewsghana',
    'custom.m4change',
    'custom.succeed',
    'custom.ucla',

    'custom.intrahealth',
    'custom.up_nrhm',

    'custom.care_pathways',
    'custom.common',

    'custom.icds',
    'custom.icds_reports',
    'custom.pnlppgi',
    'custom.nic_compliance',
    'custom.hki',
    'custom.champ',
    'custom.aaa',
)

# any built-in management commands we want to override should go in hqscripts
INSTALLED_APPS = ('hqscripts',) + DEFAULT_APPS + HQ_APPS

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
BASE_TEMPLATE = "hqwebapp/base.html"
BASE_ASYNC_TEMPLATE = "reports/async/basic.html"
LOGIN_TEMPLATE = "login_and_password/login.html"
LOGGEDOUT_TEMPLATE = LOGIN_TEMPLATE

CSRF_FAILURE_VIEW = 'corehq.apps.hqwebapp.views.csrf_failure'

# These are non-standard setting names that are used in localsettings
# The standard variables are then set to these variables after localsettings
# Todo: Change to use standard settings variables
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
SERVER_EMAIL = 'commcarehq-noreply@example.com'
DEFAULT_FROM_EMAIL = 'commcarehq-noreply@example.com'
SUPPORT_EMAIL = "support@example.com"
PROBONO_SUPPORT_EMAIL = 'pro-bono@example.com'
CCHQ_BUG_REPORT_EMAIL = 'commcarehq-bug-reports@example.com'
ACCOUNTS_EMAIL = 'accounts@example.com'
DATA_EMAIL = 'datatree@example.com'
SUBSCRIPTION_CHANGE_EMAIL = 'accounts+subchange@example.com'
INTERNAL_SUBSCRIPTION_CHANGE_EMAIL = 'accounts+subchange+internal@example.com'
BILLING_EMAIL = 'billing-comm@example.com'
INVOICING_CONTACT_EMAIL = 'billing-support@example.com'
GROWTH_EMAIL = 'growth@example.com'
MASTER_LIST_EMAIL = 'master-list@example.com'
REPORT_BUILDER_ADD_ON_EMAIL = 'sales@example.com'
EULA_CHANGE_EMAIL = 'eula-notifications@example.com'
CONTACT_EMAIL = 'info@example.com'
FEEDBACK_EMAIL = 'hq-feedback@dimagi.com'
BOOKKEEPER_CONTACT_EMAILS = []
SOFT_ASSERT_EMAIL = 'commcarehq-ops+soft_asserts@example.com'
DAILY_DEPLOY_EMAIL = None
EMAIL_SUBJECT_PREFIX = '[commcarehq] '

ENABLE_SOFT_ASSERT_EMAILS = True

SERVER_ENVIRONMENT = 'localdev'
ICDS_ENVS = ('icds', 'icds-new')
UNLIMITED_RULE_RESTART_ENVS = ('echis', 'pna', 'swiss')

# minimum minutes between updates to user reporting metadata
USER_REPORTING_METADATA_UPDATE_FREQUENCY = 15

BASE_ADDRESS = 'localhost:8000'
J2ME_ADDRESS = ''

# Set this if touchforms can't access HQ via the public URL e.g. if using a self signed cert
# Should include the protocol.
# If this is None, get_url_base() will be used
CLOUDCARE_BASE_URL = None

PAGINATOR_OBJECTS_PER_PAGE = 15
PAGINATOR_MAX_PAGE_LINKS = 5

# OTA restore fixture generators
FIXTURE_GENERATORS = [
    "corehq.apps.users.fixturegenerators.user_groups",
    "corehq.apps.fixtures.fixturegenerators.item_lists",
    "corehq.apps.callcenter.fixturegenerators.indicators_fixture_generator",
    "corehq.apps.products.fixtures.product_fixture_generator",
    "corehq.apps.programs.fixtures.program_fixture_generator",
    "corehq.apps.app_manager.fixtures.report_fixture_generator",
    "corehq.apps.app_manager.fixtures.report_fixture_v2_generator",
    "corehq.apps.calendar_fixture.fixture_provider.calendar_fixture_generator",
    "corehq.apps.locations.fixtures.location_fixture_generator",
    "corehq.apps.locations.fixtures.flat_location_fixture_generator",
    "corehq.apps.locations.fixtures.related_locations_fixture_generator",
    "custom.m4change.fixtures.report_fixtures.generator",
    "custom.m4change.fixtures.location_fixtures.generator",
]

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
CELERY_BROKER_URL = 'redis://localhost:6379/0'

# https://github.com/celery/celery/issues/4226
CELERY_BROKER_POOL_LIMIT = None

CELERY_RESULT_BACKEND = 'django-db'

CELERY_TASK_ANNOTATIONS = {
    '*': {
        'on_failure': helper.celery_failure_handler,
        'trail': False,
    }
}

CELERY_MAIN_QUEUE = 'celery'
CELERY_PERIODIC_QUEUE = 'celery_periodic'
CELERY_REMINDER_RULE_QUEUE = 'reminder_rule_queue'
CELERY_REMINDER_CASE_UPDATE_QUEUE = 'reminder_case_update_queue'
CELERY_REPEAT_RECORD_QUEUE = 'repeat_record_queue'

# Will cause a celery task to raise a SoftTimeLimitExceeded exception if
# time limit is exceeded.
CELERY_TASK_SOFT_TIME_LIMIT = 86400 * 2  # 2 days in seconds

# http://docs.celeryproject.org/en/3.1/configuration.html#celery-event-queue-ttl
# Keep messages in the events queue only for 2 hours
CELERY_EVENT_QUEUE_TTL = 2 * 60 * 60

CELERY_TASK_SERIALIZER = 'json'  # Default value in celery 4.x
CELERY_ACCEPT_CONTENT = ['json', 'pickle']  # Defaults to ['json'] in celery 4.x.  Remove once pickle is not used.

# in seconds
CELERY_HEARTBEAT_THRESHOLDS = {
    "analytics_queue": 30 * 60,
    "async_restore_queue": 60,
    "background_queue": None,
    "case_import_queue": 60,
    "case_rule_queue": None,
    "celery": 60,
    "celery_periodic": None,
    "email_queue": 30,
    "export_download_queue": 30,
    "icds_aggregation_queue": None,
    "icds_dashboard_reports_queue": None,
    "ils_gateway_sms_queue": None,
    "logistics_background_queue": None,
    "logistics_reminder_queue": None,
    "reminder_case_update_queue": 15 * 60,
    "reminder_queue": 15 * 60,
    "reminder_rule_queue": 15 * 60,
    "repeat_record_queue": 60 * 60,
    "saved_exports_queue": 6 * 60 * 60,
    "send_report_throttled": 6 * 60 * 60,
    "sms_queue": 5 * 60,
    "submission_reprocessing_queue": 60 * 60,
    "sumologic_logs_queue": 6 * 60 * 60,
    "ucr_indicator_queue": None,
    "ucr_queue": None,
}

# websockets config
WEBSOCKET_URL = '/ws/'
WS4REDIS_PREFIX = 'ws'
WSGI_APPLICATION = 'ws4redis.django_runserver.application'
WS4REDIS_ALLOWED_CHANNELS = helper.get_allowed_websocket_channels


TEST_RUNNER = 'testrunner.TwoStageTestRunner'
# this is what gets appended to @domain after your accounts
HQ_ACCOUNT_ROOT = "commcarehq.org"

FORMPLAYER_URL = 'http://localhost:8080'

####### SMS Queue Settings #######

CUSTOM_PROJECT_SMS_QUEUES = {
    'ils-gateway': 'ils_gateway_sms_queue',
    'ils-gateway-train': 'ils_gateway_sms_queue',
    'ils-gateway-training': 'ils_gateway_sms_queue',
}

# Setting this to False will make the system process outgoing and incoming SMS
# immediately rather than use the queue.
# This should always be set to True in production environments, and the sms_queue
# celery worker(s) should be deployed. We set this to False for tests and (optionally)
# for local testing.
SMS_QUEUE_ENABLED = True

# Number of minutes a celery task will alot for itself (via lock timeout)
SMS_QUEUE_PROCESSING_LOCK_TIMEOUT = 5

# Number of minutes to wait before retrying an unsuccessful processing attempt
# for a single SMS
SMS_QUEUE_REPROCESS_INTERVAL = 5

# Number of minutes to wait before retrying an SMS that has reached
# the default maximum number of processing attempts
SMS_QUEUE_REPROCESS_INDEFINITELY_INTERVAL = 60 * 6

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

PILLOW_RETRY_QUEUE_ENABLED = False

SUBMISSION_REPROCESSING_QUEUE_ENABLED = True

####### auditcare parameters #######
AUDIT_MODEL_SAVE = [
    'corehq.apps.app_manager.Application',
    'corehq.apps.app_manager.RemoteApp',
]

AUDIT_VIEWS = [
    'corehq.apps.settings.views.ChangeMyPasswordView',
    'corehq.apps.hqadmin.views.users.AuthenticateAs',
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
    'GTM_ID': '',
    'DRIFT_ID': '',
    'APPCUES_ID': '',
    'APPCUES_KEY': '',
}

ANALYTICS_CONFIG = {
    "HQ_INSTANCE": '',  # e.g. "www" or "staging"
    "DEBUG": False,
    "LOG_LEVEL": "warning",     # "warning", "debug", "verbose", or "" for no logging
}

GREENHOUSE_API_KEY = ''

MAPBOX_ACCESS_TOKEN = 'pk.eyJ1IjoiZGltYWdpIiwiYSI6ImpZWWQ4dkUifQ.3FNy5rVvLolWLycXPxKVEA'

OPEN_EXCHANGE_RATES_API_ID = ''

# for touchforms maps
GMAPS_API_KEY = "changeme"

# import local settings if we find them
LOCAL_APPS = ()
LOCAL_MIDDLEWARE = ()
LOCAL_PILLOWTOPS = {}

# tuple of fully qualified repeater class names that are enabled.
# Set to None to enable all or empty tuple to disable all.
REPEATERS_WHITELIST = None

# If ENABLE_PRELOGIN_SITE is set to true, redirect to Dimagi.com urls
ENABLE_PRELOGIN_SITE = False

# dimagi.com urls
PRICING_PAGE_URL = "https://www.dimagi.com/commcare/pricing/"

# Sumologic log aggregator
SUMOLOGIC_URL = None

# on both a single instance or distributed setup this should assume localhost
ELASTICSEARCH_HOST = 'localhost'
ELASTICSEARCH_PORT = 9200

BITLY_LOGIN = ''
BITLY_APIKEY = ''

# this should be overridden in localsettings
INTERNAL_DATA = defaultdict(list)

COUCH_STALE_QUERY = 'update_after'  # 'ok' for cloudant
# Run reindex every 10 minutes (by default)
COUCH_REINDEX_SCHEDULE = {'timedelta': {'minutes': 10}}

MESSAGE_LOG_OPTIONS = {
    "abbreviated_phone_number_domains": ["mustmgh", "mgh-cgh-uganda"],
}

PREVIEWER_RE = '^$'

MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'

DIGEST_LOGIN_FACTORY = 'django_digest.NoEmailLoginFactory'

# Django Compressor
COMPRESS_PRECOMPILERS = (
    ('text/less', 'corehq.apps.hqwebapp.precompilers.LessFilter'),
)
COMPRESS_ENABLED = True
COMPRESS_JS_COMPRESSOR = 'corehq.apps.hqwebapp.uglify.JsUglifySourcemapCompressor'
# use 'compressor.js.JsCompressor' for faster local compressing (will get rid of source maps)
COMPRESS_CSS_FILTERS = ['compressor.filters.css_default.CssAbsoluteFilter',
'compressor.filters.cssmin.rCSSMinFilter']

LESS_B3_PATHS = {
    'variables': '../../../hqwebapp/less/_hq/includes/variables',
    'mixins': '../../../hqwebapp/less/_hq/includes/mixins',
}

USER_AGENTS_CACHE = 'default'

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

# mapping of report engine IDs to database configurations
# values must be an alias of a DB in the Django DB configuration
# or a dict of the following format:
# {
#     'WRITE': 'django_db_alias',
#     'READ': [('django_db_alias', query_weighting_int), (...)]
# }
REPORTING_DATABASES = {
    'default': 'default',
    'ucr': 'default'
}

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

DATADOG_API_KEY = None
DATADOG_APP_KEY = None

SYNCLOGS_SQL_DB_ALIAS = 'default'
WAREHOUSE_DATABASE_ALIAS = 'default'

# A dict of django apps in which the reads are
# split betweeen the primary and standby db machines
# Example format:
# {
# "users":
#     [
#      ("pgmain", 5),
#      ("pgmainstandby", 5)
#     ]
# }
LOAD_BALANCED_APPS = {}

# Override with the PEM export of an RSA private key, for use with any
# encryption or signing workflows.
HQ_PRIVATE_KEY = None

# Settings for Zipline integration
ZIPLINE_API_URL = ''
ZIPLINE_API_USER = ''
ZIPLINE_API_PASSWORD = ''

# Set to the list of domain names for which we will run the ICDS SMS indicators
ICDS_SMS_INDICATOR_DOMAINS = []

KAFKA_BROKERS = ['localhost:9092']
KAFKA_API_VERSION = None

MOBILE_INTEGRATION_TEST_TOKEN = None

COMMCARE_HQ_NAME = {
    "default": "CommCare HQ",
}
COMMCARE_NAME = {
    "default": "CommCare",
}

ENTERPRISE_MODE = False

RESTRICT_DOMAIN_CREATION = False

CUSTOM_LANDING_PAGE = False

TABLEAU_URL_ROOT = "https://icds.commcarehq.org/"

SENTRY_PUBLIC_KEY = None
SENTRY_PRIVATE_KEY = None
SENTRY_PROJECT_ID = None
SENTRY_QUERY_URL = 'https://sentry.io/{org}/{project}/?query='
SENTRY_API_KEY = None

OBFUSCATE_PASSWORD_FOR_NIC_COMPLIANCE = False
RESTRICT_USED_PASSWORDS_FOR_NIC_COMPLIANCE = False
DATA_UPLOAD_MAX_MEMORY_SIZE = None
# Exports use a lot of fields to define columns. See: https://dimagi-dev.atlassian.net/browse/HI-365
DATA_UPLOAD_MAX_NUMBER_FIELDS = 5000

AUTHPROXY_URL = None
AUTHPROXY_CERT = None

# number of docs for UCR to queue asynchronously at once
# ideally # of documents it takes to process in ~30 min
ASYNC_INDICATORS_TO_QUEUE = 10000
ASYNC_INDICATOR_QUEUE_TIMES = None
DAYS_TO_KEEP_DEVICE_LOGS = 60
NO_DEVICE_LOG_ENVS = list(ICDS_ENVS) + ['production']

UCR_COMPARISONS = {}

MAX_RULE_UPDATES_IN_ONE_RUN = 10000

# used for providing separate landing pages for different URLs
# default will be used if no hosts match
CUSTOM_LANDING_TEMPLATE = {
    # "icds-cas.gov.in": 'icds/login.html',
    # "default": 'login_and_password/login.html',
}

ES_SETTINGS = None

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
    if six.text_type(error) != 'No module named localsettings':
        raise error
    # fallback in case nothing else is found - used for readthedocs
    from dev_settings import *


# Unless DISABLE_SERVER_SIDE_CURSORS has explicitly been set, default to True because Django >= 1.11.1 and our
# hosting environments use pgBouncer with transaction pooling. For more information, see:
# https://docs.djangoproject.com/en/1.11/releases/1.11.1/#allowed-disabling-server-side-cursors-on-postgresql
for database in DATABASES.values():
    if (
        database['ENGINE'] == 'django.db.backends.postgresql_psycopg2' and
        database.get('DISABLE_SERVER_SIDE_CURSORS') is None
    ):
        database['DISABLE_SERVER_SIDE_CURSORS'] = True


_location = lambda x: os.path.join(FILEPATH, x)

IS_SAAS_ENVIRONMENT = SERVER_ENVIRONMENT in ('production', 'staging')

if 'KAFKA_URL' in globals():
    import warnings
    warnings.warn(inspect.cleandoc("""KAFKA_URL is deprecated

    Please replace KAFKA_URL with KAFKA_BROKERS as follows:

        KAFKA_BROKERS = ['%s']
    """) % KAFKA_URL, DeprecationWarning)

    KAFKA_BROKERS = [KAFKA_URL]

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
                'django.template.context_processors.debug',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.request',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',

                'corehq.util.context_processors.base_template',
                'corehq.util.context_processors.current_url_name',
                'corehq.util.context_processors.domain',
                'corehq.util.context_processors.domain_billing_context',
                'corehq.util.context_processors.enterprise_mode',
                'corehq.util.context_processors.mobile_experience',
                'corehq.util.context_processors.get_demo',
                'corehq.util.context_processors.js_api_keys',
                'corehq.util.context_processors.js_toggles',
                'corehq.util.context_processors.websockets_override',
                'corehq.util.context_processors.commcare_hq_names',
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
            'format': '%(asctime)s [%(username)s:%(domain)s] %(hq_url)s %(database)s %(method)s %(status_code)s %(content_length)s %(path)s %(duration)s'
        },
        'formplayer_timing': {
            'format': '%(asctime)s, %(action)s, %(control_duration)s, %(candidate_duration)s'
        },
        'formplayer_diff': {
            'format': '%(asctime)s, %(action)s, %(request)s, %(control)s, %(candidate)s'
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
        'exclude_static': {
            '()': 'corehq.util.log.SuppressStaticLogs',
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
        'formplayer_diff': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'formplayer_diff',
            'filename': FORMPLAYER_DIFF_FILE,
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 20  # Backup 200 MB of logs
        },
        'formplayer_timing': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'formplayer_timing',
            'filename': FORMPLAYER_TIMING_FILE,
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
        'sentry': {
            'level': 'ERROR',
            'class': 'raven.contrib.django.raven_compat.handlers.SentryHandler',
        },
        'soft_asserts': {
            "level": "DEBUG",
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'verbose',
            'filename': SOFT_ASSERTS_LOG_FILE,
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 200  # Backup 2000 MB of logs
        },
        'main_couch_sql_datamigration': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'simple',
            'filename': MAIN_COUCH_SQL_DATAMIGRATION,
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 20
        },
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console', 'file'],
    },
    'loggers': {
        'couchdbkit.request': {
            'handlers': ['couch-request-handler'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'django': {
            'handlers': ['sentry'],
            'level': 'ERROR',
            'propagate': True,
        },
        'django.server': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
            'filters': ['exclude_static'],
        },
        'django.security.DisallowedHost': {
            'handlers': ['null'],
            'propagate': False,
        },
        'notify': {
            'handlers': ['sentry'],
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
            'level': 'INFO',
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
        'formplayer_timing': {
            'handlers': ['formplayer_timing'],
            'level': 'INFO',
            'propogate': True,
        },
        'formplayer_diff': {
            'handlers': ['formplayer_diff'],
            'level': 'INFO',
            'propogate': True,
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
        'sentry.errors.uncaught': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'soft_asserts': {
            'handlers': ['soft_asserts', 'console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'kafka': {
            'handlers': ['file'],
            'level': 'ERROR',
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


DATABASE_ROUTERS = globals().get('DATABASE_ROUTERS', [])
if 'corehq.sql_db.routers.MultiDBRouter' not in DATABASE_ROUTERS:
    DATABASE_ROUTERS.append('corehq.sql_db.routers.MultiDBRouter')

INDICATOR_CONFIG = {
}

COMPRESS_URL = STATIC_CDN + STATIC_URL

####### Couch Forms & Couch DB Kit Settings #######
if six.PY3:
    NEW_USERS_GROUPS_DB = 'users'
    USERS_GROUPS_DB = NEW_USERS_GROUPS_DB

    NEW_FIXTURES_DB = 'fixtures'
    FIXTURES_DB = NEW_FIXTURES_DB

    NEW_DOMAINS_DB = 'domains'
    DOMAINS_DB = NEW_DOMAINS_DB

    NEW_APPS_DB = 'apps'
    APPS_DB = NEW_APPS_DB

    META_DB = 'meta'

    _serializer = 'corehq.util.python_compatibility.Py3PickleSerializer'
    for _name in ["default", "redis"]:
        if _name not in CACHES:  # noqa: F405
            continue
        _options = CACHES[_name].setdefault('OPTIONS', {})  # noqa: F405
        assert _options.get('SERIALIZER', _serializer) == _serializer, (
            "Refusing to change SERIALIZER. Remove that option from "
            "localsettings or whereever redis caching is configured. {}"
            .format(_options)
        )
        _options['SERIALIZER'] = _serializer
    del _name, _options, _serializer
else:
    NEW_USERS_GROUPS_DB = b'users'
    USERS_GROUPS_DB = NEW_USERS_GROUPS_DB

    NEW_FIXTURES_DB = b'fixtures'
    FIXTURES_DB = NEW_FIXTURES_DB

    NEW_DOMAINS_DB = b'domains'
    DOMAINS_DB = NEW_DOMAINS_DB

    NEW_APPS_DB = b'apps'
    APPS_DB = NEW_APPS_DB

    META_DB = b'meta'


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
    'dhis2',
    'ext',
    'facilities',
    'fluff_filter',
    'hqcase',
    'hqmedia',
    'case_importer',
    'indicators',
    'locations',
    'mobile_auth',
    'openmrs',
    'pillowtop',
    'pillow_retry',
    'products',
    'programs',
    'reminders',
    'reports',
    'saved_reports',
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
    'crs_reports',
    'grapevine',
    'openclinica',

    # custom reports
    'hsph',
    'pact',
    'accounting',
    'succeed',
    'ilsgateway',
    'ewsghana',
    ('auditcare', 'auditcare'),
    ('repeaters', 'receiverwrapper'),
    ('userreports', META_DB),
    ('custom_data_fields', META_DB),
    # needed to make couchdbkit happy
    ('fluff', 'fluff-bihar'),
    ('mc', 'fluff-mc'),
    ('m4change', 'm4change'),
    ('export', META_DB),
    ('callcenter', META_DB),

    # users and groups
    ('groups', USERS_GROUPS_DB),
    ('users', USERS_GROUPS_DB),

    # fixtures
    ('fixtures', FIXTURES_DB),

    # domains
    ('domain', DOMAINS_DB),

    # applications
    ('app_manager', APPS_DB),
]

COUCH_SETTINGS_HELPER = helper.CouchSettingsHelper(
    COUCH_DATABASES,
    COUCHDB_APPS,
    [NEW_USERS_GROUPS_DB, NEW_FIXTURES_DB, NEW_DOMAINS_DB, NEW_APPS_DB],
    UNIT_TESTING
)
COUCH_DATABASE = COUCH_SETTINGS_HELPER.main_db_url
COUCHDB_DATABASES = COUCH_SETTINGS_HELPER.make_couchdb_tuples()
EXTRA_COUCHDB_DATABASES = COUCH_SETTINGS_HELPER.get_extra_couchdbs()

# note: the only reason LOCAL_APPS come before INSTALLED_APPS is because of
# a weird travis issue with kafka. if for any reason this order causes problems
# it can be reverted whenever that's figured out.
# https://github.com/dimagi/commcare-hq/pull/10034#issuecomment-174868270
INSTALLED_APPS = LOCAL_APPS + INSTALLED_APPS

seen = set()
INSTALLED_APPS = [x for x in INSTALLED_APPS if x not in seen and not seen.add(x)]

MIDDLEWARE += LOCAL_MIDDLEWARE
if 'icds-ucr' in DATABASES:
    MIDDLEWARE.append('custom.icds_reports.middleware.ICDSAuditMiddleware')

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
    messages.WARNING: 'alert-warning',
    messages.ERROR: 'alert-danger',
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
    'corehq.messaging.smsbackends.starfish.models.StarfishBackend',
    'corehq.messaging.smsbackends.sislog.models.SQLSislogBackend',
    'corehq.messaging.smsbackends.smsgh.models.SQLSMSGHBackend',
    'corehq.messaging.smsbackends.telerivet.models.SQLTelerivetBackend',
    'corehq.messaging.smsbackends.test.models.SQLTestSMSBackend',
    'corehq.messaging.smsbackends.tropo.models.SQLTropoBackend',
    'corehq.messaging.smsbackends.twilio.models.SQLTwilioBackend',
    'corehq.messaging.smsbackends.unicel.models.SQLUnicelBackend',
    'corehq.messaging.smsbackends.yo.models.SQLYoBackend',
    'corehq.messaging.smsbackends.vertex.models.VertexBackend',
    'corehq.messaging.smsbackends.start_enterprise.models.StartEnterpriseBackend',
    'corehq.messaging.smsbackends.ivory_coast_mtn.models.IvoryCoastMTNBackend',
    'corehq.messaging.smsbackends.karix.models.KarixBackend',
    'corehq.messaging.smsbackends.airtel_tcl.models.AirtelTCLBackend',
]

# The number of seconds to use as a timeout when making gateway requests
SMS_GATEWAY_TIMEOUT = 5

# These are functions that can be called
# to retrieve custom content in a reminder event.
# If the function is not in here, it will not be called.
# Used by the old reminders framework
ALLOWED_CUSTOM_CONTENT_HANDLERS = {
    "UCLA_GENERAL_HEALTH": "custom.ucla.api.general_health_message_bank_content",
    "UCLA_MENTAL_HEALTH": "custom.ucla.api.mental_health_message_bank_content",
    "UCLA_SEXUAL_HEALTH": "custom.ucla.api.sexual_health_message_bank_content",
    "UCLA_MED_ADHERENCE": "custom.ucla.api.med_adherence_message_bank_content",
    "UCLA_SUBSTANCE_USE": "custom.ucla.api.substance_use_message_bank_content",
}

# Used by the new reminders framework
AVAILABLE_CUSTOM_SCHEDULING_CONTENT = {
    "ICDS_STATIC_NEGATIVE_GROWTH_MESSAGE":
        ["custom.icds.messaging.custom_content.static_negative_growth_indicator",
         "ICDS: Static/Negative Growth Indicator"],
    "ICDS_MISSED_CF_VISIT_TO_AWW":
        ["custom.icds.messaging.custom_content.missed_cf_visit_to_aww",
         "ICDS: Missed CF Visit for AWW recipient"],
    "ICDS_MISSED_CF_VISIT_TO_LS":
        ["custom.icds.messaging.custom_content.missed_cf_visit_to_ls",
         "ICDS: Missed CF Visit for LS recipient"],
    "ICDS_MISSED_PNC_VISIT_TO_LS":
        ["custom.icds.messaging.custom_content.missed_pnc_visit_to_ls",
         "ICDS: Missed PNC Visit for LS recipient"],
    "ICDS_CHILD_ILLNESS_REPORTED":
        ["custom.icds.messaging.custom_content.child_illness_reported",
         "ICDS: Child Illness Reported"],
    "ICDS_CF_VISITS_COMPLETE":
        ["custom.icds.messaging.custom_content.cf_visits_complete",
         "ICDS: CF Visits Complete"],
    "ICDS_AWW_1":
        ["custom.icds.messaging.custom_content.aww_1",
         "ICDS: Weekly AWC Submission Performance to AWW"],
    "ICDS_AWW_2":
        ["custom.icds.messaging.custom_content.aww_2",
         "ICDS: Monthly AWC Aggregate Performance to AWW"],
    "ICDS_LS_1":
        ["custom.icds.messaging.custom_content.ls_1",
         "ICDS: Monthly AWC Aggregate Performance to LS"],
    "ICDS_LS_2":
        ["custom.icds.messaging.custom_content.ls_2",
         "ICDS: Weekly AWC VHND Performance to LS"],
    "ICDS_LS_6":
        ["custom.icds.messaging.custom_content.ls_6",
         "ICDS: Weekly AWC Submission Performance to LS"],
    "ICDS_PHASE2_AWW_1":
        ["custom.icds.messaging.custom_content.phase2_aww_1",
         "ICDS: AWC VHND Performance to AWW"],
    "UCLA_GENERAL_HEALTH":
        ["custom.ucla.api.general_health_message_bank_content_new",
         "UCLA: General Health Message Bank"],
    "UCLA_MENTAL_HEALTH":
        ["custom.ucla.api.mental_health_message_bank_content_new",
         "UCLA: Mental Health Message Bank"],
    "UCLA_SEXUAL_HEALTH":
        ["custom.ucla.api.sexual_health_message_bank_content_new",
         "UCLA: Sexual Health Message Bank"],
    "UCLA_MED_ADHERENCE":
        ["custom.ucla.api.med_adherence_message_bank_content_new",
         "UCLA: Med Adherence Message Bank"],
    "UCLA_SUBSTANCE_USE":
        ["custom.ucla.api.substance_use_message_bank_content_new",
         "UCLA: Substance Use Message Bank"],
}

# Used by the old reminders framework
AVAILABLE_CUSTOM_REMINDER_RECIPIENTS = {
    'HOST_CASE_OWNER_LOCATION':
        ['corehq.apps.reminders.custom_recipients.host_case_owner_location',
         "Custom: Extension Case -> Host Case -> Owner (which is a location)"],
    'HOST_CASE_OWNER_LOCATION_PARENT':
        ['corehq.apps.reminders.custom_recipients.host_case_owner_location_parent',
         "Custom: Extension Case -> Host Case -> Owner (which is a location) -> Parent location"],
    'CASE_OWNER_LOCATION_PARENT':
        ['custom.abt.messaging.custom_recipients.abt_case_owner_location_parent_old_framework',
         "Abt: The case owner's location's parent location"],
}

# Used by the new reminders framework
AVAILABLE_CUSTOM_SCHEDULING_RECIPIENTS = {
    'ICDS_MOTHER_PERSON_CASE_FROM_CCS_RECORD_CASE':
        ['custom.icds.messaging.custom_recipients.recipient_mother_person_case_from_ccs_record_case',
         "ICDS: Mother person case from ccs_record case"],
    'ICDS_MOTHER_PERSON_CASE_FROM_CCS_RECORD_CASE_EXCL_MIGRATED_OR_OPTED_OUT':
        ['custom.icds.messaging.custom_recipients'
         '.recipient_mother_person_case_from_ccs_record_case_excl_migrated_or_opted_out',
         "ICDS: Mother person case from ccs_record case (excluding migrated and not registered mothers)"],
    'ICDS_MOTHER_PERSON_CASE_FROM_CHILD_HEALTH_CASE':
        ['custom.icds.messaging.custom_recipients.recipient_mother_person_case_from_child_health_case',
         "ICDS: Mother person case from child_health case"],
    'ICDS_MOTHER_PERSON_CASE_FROM_CHILD_PERSON_CASE':
        ['custom.icds.messaging.custom_recipients.recipient_mother_person_case_from_child_person_case',
         "ICDS: Mother person case from child person case"],
    'ICDS_SUPERVISOR_FROM_AWC_OWNER':
        ['custom.icds.messaging.custom_recipients.supervisor_from_awc_owner',
         "ICDS: Supervisor Location from AWC Owner"],
    'HOST_CASE_OWNER_LOCATION':
        ['corehq.messaging.scheduling.custom_recipients.host_case_owner_location',
         "Custom: Extension Case -> Host Case -> Owner (which is a location)"],
    'HOST_CASE_OWNER_LOCATION_PARENT':
        ['corehq.messaging.scheduling.custom_recipients.host_case_owner_location_parent',
         "Custom: Extension Case -> Host Case -> Owner (which is a location) -> Parent location"],
    'CASE_OWNER_LOCATION_PARENT':
        ['custom.abt.messaging.custom_recipients.abt_case_owner_location_parent_new_framework',
         "Abt: The case owner's location's parent location"],
}

AVAILABLE_CUSTOM_RULE_CRITERIA = {
    'ICDS_PERSON_CASE_IS_UNDER_6_YEARS_OLD':
        'custom.icds.rules.custom_criteria.person_case_is_under_6_years_old',
    'ICDS_PERSON_CASE_IS_UNDER_19_YEARS_OLD':
        'custom.icds.rules.custom_criteria.person_case_is_under_19_years_old',
    'ICDS_CCS_RECORD_CASE_HAS_FUTURE_EDD':
        'custom.icds.rules.custom_criteria.ccs_record_case_has_future_edd',
    'ICDS_IS_USERCASE_OF_AWW':
        'custom.icds.rules.custom_criteria.is_usercase_of_aww',
    'ICDS_IS_USERCASE_OF_LS':
        'custom.icds.rules.custom_criteria.is_usercase_of_ls',
}

AVAILABLE_CUSTOM_RULE_ACTIONS = {
    'ICDS_ESCALATE_TECH_ISSUE':
        'custom.icds.rules.custom_actions.escalate_tech_issue',
}

# These are custom templates which can wrap default the sms/chat.html template
CUSTOM_CHAT_TEMPLATES = {}

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
            'name': 'case-pillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.pillows.case.get_case_pillow',
            'params': {
                'ucr_division': '0f'
            }
        },
        {
            'name': 'xform-pillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.pillows.xform.get_xform_pillow',
            'params': {
                'ucr_division': '0f'
            }
        },
        {
            'name': 'UserPillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.pillows.user.get_user_pillow_old',
        },
        {
            'name': 'user-pillow',
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
            'instance': 'corehq.pillows.group.get_group_pillow_old',
        },
        {
            'name': 'GroupToUserPillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.pillows.groups_to_user.get_group_to_user_pillow',
        },
        {
            'name': 'group-pillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.pillows.groups_to_user.get_group_pillow',
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
            'name': 'FormSubmissionMetadataTrackerPillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.pillows.app_submission_tracker.get_form_submission_metadata_tracker_pillow',
        },
        {
            'name': 'UpdateUserSyncHistoryPillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.pillows.synclog.get_user_sync_history_pillow',
        },
        {
            'name': 'kafka-ucr-main',
            'class': 'corehq.apps.userreports.pillow.ConfigurableReportKafkaPillow',
            'instance': 'corehq.apps.userreports.pillow.get_kafka_ucr_pillow',
            'params': {
                'ucr_division': '0f'
            }
        },
        {
            'name': 'kafka-ucr-static',
            'class': 'corehq.apps.userreports.pillow.ConfigurableReportKafkaPillow',
            'instance': 'corehq.apps.userreports.pillow.get_kafka_ucr_static_pillow',
            'params': {
                'ucr_division': '0f'
            }
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
            'name': 'location-ucr-pillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.apps.userreports.pillow.get_location_pillow',
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
        'custom.m4change.models.M4ChangeFormFluffPillow',
        'custom.intrahealth.models.IntraHealthFormFluffPillow',
        'custom.intrahealth.models.RecouvrementFluffPillow',
        'custom.care_pathways.models.GeographyFluffPillow',
        'custom.care_pathways.models.FarmerRecordFluffPillow',
        'custom.succeed.models.UCLAPatientFluffPillow',
    ],
    'experimental': [
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

REPEATERS = (
    'corehq.motech.repeaters.models.FormRepeater',
    'corehq.motech.repeaters.models.CaseRepeater',
    'corehq.motech.repeaters.models.CreateCaseRepeater',
    'corehq.motech.repeaters.models.UpdateCaseRepeater',
    'corehq.motech.repeaters.models.ShortFormRepeater',
    'corehq.motech.repeaters.models.AppStructureRepeater',
    'corehq.motech.repeaters.models.UserRepeater',
    'corehq.motech.repeaters.models.LocationRepeater',
    'corehq.motech.openmrs.repeaters.OpenmrsRepeater',
    'corehq.motech.dhis2.repeaters.Dhis2Repeater',
)


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
    os.path.join('custom', 'abt', 'reports', 'supervisory_report_v2.json'),
    os.path.join('custom', 'abt', 'reports', 'supervisory_report_v2019.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'dashboard', '*.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'asr', '*.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'asr', 'ucr_v2', '*.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'mpr', '*.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'mpr', 'dashboard', '*.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'mpr', 'testing', '*.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'mpr', 'ucr_v2', '*.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'ls', '*.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'reports', 'other', '*.json'),
    os.path.join('custom', 'echis_reports', 'ucr', 'reports', '*.json'),
    os.path.join('custom', 'aaa', 'ucr', 'reports', '*.json'),
]


STATIC_DATA_SOURCES = [
    os.path.join('custom', 'up_nrhm', 'data_sources', 'location_hierarchy.json'),
    os.path.join('custom', 'up_nrhm', 'data_sources', 'asha_facilitators.json'),
    os.path.join('custom', 'succeed', 'data_sources', 'submissions.json'),
    os.path.join('custom', 'succeed', 'data_sources', 'patient_task_list.json'),
    os.path.join('custom', 'abt', 'reports', 'data_sources', 'sms_case.json'),
    os.path.join('custom', 'abt', 'reports', 'data_sources', 'supervisory.json'),
    os.path.join('custom', 'abt', 'reports', 'data_sources', 'supervisory_v2.json'),
    os.path.join('custom', 'abt', 'reports', 'data_sources', 'supervisory_v2019.json'),
    os.path.join('custom', 'abt', 'reports', 'data_sources', 'late_pmt.json'),
    os.path.join('custom', '_legacy', 'mvp', 'ucr', 'reports', 'data_sources', 'va_datasource.json'),
    os.path.join('custom', 'reports', 'mc', 'data_sources', 'malaria_consortium.json'),
    os.path.join('custom', 'reports', 'mc', 'data_sources', 'weekly_forms.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'awc_locations.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'awc_mgt_forms.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'ccs_record_cases.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'ccs_record_cases_monthly_v2.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'child_cases_monthly_v2.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'child_delivery_forms.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'child_health_cases.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'daily_feeding_forms.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'gm_forms.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'hardware_cases.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'home_visit_forms.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'household_cases.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'infrastructure_form.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'infrastructure_form_v2.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'it_report_follow_issue.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'ls_home_visit_forms_filled.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'ls_vhnd_form.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'person_cases_v3.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'tasks_cases.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'tech_issue_cases.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'thr_forms_v2.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'usage_forms.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'vhnd_form.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'visitorbook_forms.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'dashboard', 'complementary_feeding_forms.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'dashboard', 'dashboard_growth_monitoring.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'dashboard', 'postnatal_care_forms.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'dashboard', 'commcare_user_cases.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'dashboard', 'delivery_forms.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'dashboard', 'pregnant_tasks.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'dashboard', 'child_tasks.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'dashboard', 'thr_forms.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'dashboard', 'birth_preparedness_forms.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'dashboard', 'daily_feeding_forms.json'),
    os.path.join('custom', 'icds_reports', 'ucr', 'data_sources', 'cbe_form.json'),
    os.path.join('custom', 'pnlppgi', 'resources', 'site_reporting_rates.json'),
    os.path.join('custom', 'pnlppgi', 'resources', 'malaria.json'),
    os.path.join('custom', 'champ', 'ucr_data_sources', 'champ_cameroon.json'),
    os.path.join('custom', 'champ', 'ucr_data_sources', 'enhanced_peer_mobilization.json'),
    os.path.join('custom', 'intrahealth', 'ucr', 'data_sources', 'commande_combined.json'),
    os.path.join('custom', 'intrahealth', 'ucr', 'data_sources', 'livraison_combined.json'),
    os.path.join('custom', 'intrahealth', 'ucr', 'data_sources', 'operateur_combined.json'),
    os.path.join('custom', 'intrahealth', 'ucr', 'data_sources', 'rapture_combined.json'),
    os.path.join('custom', 'intrahealth', 'ucr', 'data_sources', 'recouvrement_combined.json'),
    os.path.join('custom', 'intrahealth', 'ucr', 'data_sources', 'visite_de_l_operateur.json'),
    os.path.join('custom', 'intrahealth', 'ucr', 'data_sources', 'visite_de_l_operateur_per_product.json'),
    os.path.join('custom', 'intrahealth', 'ucr', 'data_sources', 'yeksi_naa_reports_logisticien.json'),
    os.path.join('custom', 'intrahealth', 'ucr', 'data_sources', 'visite_de_l_operateur_per_program.json'),
    os.path.join('custom', 'intrahealth', 'ucr', 'data_sources', 'visite_de_l_operateur_product_consumption.json'),

    os.path.join('custom', 'echis_reports', 'ucr', 'data_sources', '*.json'),
    os.path.join('custom', 'aaa', 'ucr', 'data_sources', '*.json'),
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
    'hsph-dev',
    'hsph-betterbirth-pilot-2',
    'commtrack-public-demo',
    'crs-remind',
    'succeed',
]

# Custom fully indexed domains for ReportXForm index/pillowtop --
# only those domains that don't require custom pre-processing before indexing,
# otherwise list in XFORM_PILLOW_HANDLERS
# Adding a domain will not automatically index that domain's existing forms
ES_XFORM_FULL_INDEX_DOMAINS = [
    'commtrack-public-demo',
    'pact',
    'succeed'
]

CUSTOM_UCR_EXPRESSIONS = [
    ('abt_supervisor', 'custom.abt.reports.expressions.abt_supervisor_expression'),
    ('abt_supervisor_v2', 'custom.abt.reports.expressions.abt_supervisor_v2_expression'),
    ('abt_supervisor_v2019', 'custom.abt.reports.expressions.abt_supervisor_v2019_expression'),
    ('succeed_referenced_id', 'custom.succeed.expressions.succeed_referenced_id'),
    ('location_type_name', 'corehq.apps.locations.ucr_expressions.location_type_name'),
    ('location_parent_id', 'corehq.apps.locations.ucr_expressions.location_parent_id'),
    ('ancestor_location', 'corehq.apps.locations.ucr_expressions.ancestor_location'),
    ('eqa_expression', 'custom.eqa.expressions.eqa_expression'),
    ('cqi_action_item', 'custom.eqa.expressions.cqi_action_item'),
    ('eqa_percent_expression', 'custom.eqa.expressions.eqa_percent_expression'),
    ('year_expression', 'custom.pnlppgi.expressions.year_expression'),
    ('week_expression', 'custom.pnlppgi.expressions.week_expression'),
]

CUSTOM_UCR_EXPRESSION_LISTS = [
    ('mvp.ucr.reports.expressions.CUSTOM_UCR_EXPRESSIONS'),
    ('custom.icds_reports.ucr.expressions.CUSTOM_UCR_EXPRESSIONS'),
    ('corehq.apps.userreports.expressions.extension_expressions.CUSTOM_UCR_EXPRESSIONS'),
]

CUSTOM_UCR_REPORT_FILTERS = [
    ('village_choice_list', 'custom.icds_reports.ucr.filter_spec.build_village_choice_list_filter_spec')
]

CUSTOM_UCR_REPORT_FILTER_VALUES = [
    ('village_choice_list', 'custom.icds_reports.ucr.filter_value.VillageFilterValue')
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

DOMAIN_MODULE_MAP = {
    'hsph-dev': 'hsph',
    'hsph-betterbirth-pilot-2': 'hsph',
    'mc-inscale': 'custom.reports.mc',
    'pact': 'pact',

    'ipm-senegal': 'custom.intrahealth',
    'icds-test': 'custom.icds_reports',
    'icds-cas': 'custom.icds_reports',
    'icds-dashboard-qa': 'custom.icds_reports',
    'reach-test': 'custom.aaa',
    'reach-dashboard-qa': 'custom.aaa',
    'testing-ipm-senegal': 'custom.intrahealth',
    'up-nrhm': 'custom.up_nrhm',

    'crs-remind': 'custom.apps.crs_reports',

    'm4change': 'custom.m4change',
    'succeed': 'custom.succeed',
    'test-pathfinder': 'custom.m4change',
    'pathways-india-mis': 'custom.care_pathways',
    'pathways-tanzania': 'custom.care_pathways',
    'care-macf-malawi': 'custom.care_pathways',
    'care-macf-bangladesh': 'custom.care_pathways',
    'care-macf-ghana': 'custom.care_pathways',
    'pnlppgi': 'custom.pnlppgi',
    'champ-cameroon': 'custom.champ',

    # From DOMAIN_MODULE_CONFIG on production
    'ews-ghana': 'custom.ewsghana',
    'ews-ghana-1': 'custom.ewsghana',
    'ewsghana-6': 'custom.ewsghana',
    'ewsghana-september': 'custom.ewsghana',
    'ewsghana-test-4': 'custom.ewsghana',
    'ewsghana-test-5': 'custom.ewsghana',
    'ewsghana-test3': 'custom.ewsghana',
    # Used in tests.  TODO - use override_settings instead
    'ewsghana-test-input-stock': 'custom.ewsghana',
    'test-pna': 'custom.intrahealth',

    #vectorlink domains
    'abtmali': 'custom.abt',
    'airs': 'custom.abt',
    'airs-testing': 'custom.abt',
    'airsbenin': 'custom.abt',
    'airsethiopia': 'custom.abt',
    'airskenya': 'custom.abt',
    'airsmadagascar': 'custom.abt',
    'airsmozambique': 'custom.abt',
    'airsrwanda': 'custom.abt',
    'airstanzania': 'custom.abt',
    'airszambia': 'custom.abt',
    'airszimbabwe': 'custom.abt',
    'vectorlink-benin': 'custom.abt',
    'vectorlink-burkina-faso': 'custom.abt',
    'vectorlink-ethiopia': 'custom.abt',
    'vectorlink-ghana': 'custom.abt',
    'vectorlink-kenya': 'custom.abt',
    'vectorlink-madagascar': 'custom.abt',
    'vectorlink-malawi': 'custom.abt',
    'vectorlink-mali': 'custom.abt',
    'vectorlink-mozambique': 'custom.abt',
    'vectorlink-rwanda': 'custom.abt',
    'vectorlink-tanzania': 'custom.abt',
    'vectorlink-uganda': 'custom.abt',
    'vectorlink-zambia': 'custom.abt',
    'vectorlink-zimbabwe': 'custom.abt',
}

THROTTLE_SCHED_REPORTS_PATTERNS = (
    # Regex patterns matching domains whose scheduled reports use a
    # separate queue so that they don't hold up the background queue.
    'ews-ghana$',
    'mvp-',
)

# Domains that we want to tag in datadog
DATADOG_DOMAINS = {
    # ("env", "domain"),
    ("production", "born-on-time-2"),
    ("production", "hki-nepal-suaahara-2"),
    ("production", "malawi-fp-study"),
    ("production", "no-lean-season"),
    ("production", "rec"),
    ("production", "isth-production"),
    ("production", "sauti-1"),
}

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

if UNIT_TESTING or DEBUG or 'ddtrace.contrib.django' not in INSTALLED_APPS:
    try:
        from ddtrace import tracer
        tracer.enabled = False
    except ImportError:
        pass

REST_FRAMEWORK = {
    'DATETIME_FORMAT': '%Y-%m-%dT%H:%M:%S.%fZ',
}

SENTRY_CONFIGURED = False
_raven_config = helper.configure_sentry(
    BASE_DIR,
    SERVER_ENVIRONMENT,
    SENTRY_PUBLIC_KEY,
    SENTRY_PRIVATE_KEY,
    SENTRY_PROJECT_ID
)
if _raven_config:
    RAVEN_CONFIG = _raven_config
    SENTRY_CONFIGURED = True
    SENTRY_CLIENT = 'corehq.util.sentry.HQSentryClient'

CSRF_COOKIE_HTTPONLY = True
if RESTRICT_USED_PASSWORDS_FOR_NIC_COMPLIANCE:
    AUTH_PASSWORD_VALIDATORS = [
        {
            'NAME': 'custom.nic_compliance.password_validation.UsedPasswordValidator',
        }
    ]

PACKAGE_MONITOR_REQUIREMENTS_FILE = os.path.join(FILEPATH, 'requirements', 'requirements.txt')
