#!/usr/bin/env python
# flake8: noqa: F405

import inspect
from collections import defaultdict
import importlib
import os

from django.contrib import messages
import settingshelper as helper

DEBUG = True

# clone http://github.com/dimagi/Vellum into submodules/formdesigner and use
# this to select various versions of Vellum source on the form designer page.
# Acceptable values:
# None - production mode
# "dev" - use raw vellum source (submodules/formdesigner/src)
# "dev-min" - use built/minified vellum (submodules/formdesigner/_build/src)
VELLUM_DEBUG = None


# For Single Sign On (SSO) Implementations
SAML2_DEBUG = False
ENFORCE_SSO_LOGIN = False

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# gets set to False for unit tests that run without the database
DB_ENABLED = True
UNIT_TESTING = helper.is_testing()
DISABLE_RANDOM_TOGGLES = UNIT_TESTING

# Setting to declare always_enabled/always_disabled toggle states for domains
#   declaring toggles here avoids toggle lookups from cache for all requests.
#   Example format
#   STATIC_TOGGLE_STATES = {
#     'toggle_slug': {
#         'always_enabled': ['domain1', 'domain2],
#         'always_disabled': ['domain4', 'domain3],
#     }
#   }
STATIC_TOGGLE_STATES = {}

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
    ('por', 'Portuguese'),
)

STATICI18N_FILENAME_FUNCTION = 'statici18n.utils.legacy_filename'

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

YARN_COMPONENTS = os.path.join(FILEPATH, 'node_modules')

STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    'compressor.finders.CompressorFinder',
)

STATICFILES_DIRS = [
    YARN_COMPONENTS,
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

LOCAL_LOGGING_CONFIG = {}

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/static/admin/'

# Make this unique, and don't share it with anybody - put into localsettings.py
SECRET_KEY = 'you should really change this'

MIDDLEWARE = [
    'corehq.middleware.NoCacheMiddleware',
    'corehq.middleware.SelectiveSessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
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
    'corehq.apps.auditcare.middleware.AuditMiddleware',
    'no_exceptions.middleware.NoExceptionsMiddleware',
    'corehq.apps.locations.middleware.LocationAccessMiddleware',
    'corehq.apps.cloudcare.middleware.CloudcareMiddleware',
    # middleware that adds cookies must come before SecureCookiesMiddleware
    'corehq.middleware.SecureCookiesMiddleware',
    'field_audit.middleware.FieldAuditMiddleware',
]

X_FRAME_OPTIONS = 'DENY'

SESSION_ENGINE = "django.contrib.sessions.backends.cache"

# time in minutes before forced logout due to inactivity
INACTIVITY_TIMEOUT = 60 * 24 * 14
SECURE_TIMEOUT = 30
DISABLE_AUTOCOMPLETE_ON_SENSITIVE_FORMS = False
MINIMUM_ZXCVBN_SCORE = 2
MINIMUM_PASSWORD_LENGTH = 8
CUSTOM_PASSWORD_STRENGTH_MESSAGE = ''
ADD_CAPTCHA_FIELD_TO_FORMS = False

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'corehq.apps.domain.auth.ApiKeyFallbackBackend',
    'corehq.apps.sso.backends.SsoBackend',
    'corehq.apps.domain.auth.ConnectIDAuthBackend'
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
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

DEFAULT_APPS = (
    'corehq.apps.celery.Config',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.humanize',
    'django.contrib.messages',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.staticfiles',
    'django_celery_results',
    'django_prbac',
    'captcha',
    'couchdbkit.ext.django',
    'crispy_forms',
    'crispy_bootstrap3to5',
    'field_audit',
    'gunicorn',
    'compressor',
    'tastypie',
    'django_otp',
    'django_otp.plugins.otp_static',
    'django_otp.plugins.otp_totp',
    'two_factor',
    'two_factor.plugins.phonenumber',
    'ws4redis',
    'statici18n',
    'django_user_agents',
    'logentry_admin',
    'oauth2_provider',
)

SILENCED_SYSTEM_CHECKS = ['captcha.recaptcha_test_key_error']
RECAPTCHA_PRIVATE_KEY = ''
RECAPTCHA_PUBLIC_KEY = ''

CRISPY_TEMPLATE_PACK = 'bootstrap3to5'
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap3to5"

FIELD_AUDIT_AUDITORS = [
    "corehq.apps.users.auditors.HQAuditor",
    "field_audit.auditors.SystemUserAuditor",
]

HQ_APPS = (
    'django_digest',
    'corehq.apps.auditcare.AuditcareConfig',
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
    'corehq.apps.data_pipeline_audit',
    'corehq.apps.domain',
    'corehq.apps.domain_migration_flags',
    'corehq.apps.dump_reload',
    'corehq.apps.enterprise',
    'corehq.apps.formplayer_api',
    'corehq.apps.hqadmin.app_config.HqAdminModule',
    'corehq.apps.hqcase',
    'corehq.apps.hqwebapp.apps.HqWebAppConfig',
    'corehq.apps.hqmedia',
    'corehq.apps.integration',
    'corehq.apps.linked_domain',
    'corehq.apps.locations',
    'corehq.apps.products',
    'corehq.apps.programs',
    'corehq.apps.registry.app_config.RegistryAppConfig',
    'corehq.project_limits',
    'corehq.apps.commtrack',
    'corehq.apps.consumption',
    'corehq.celery_monitoring.app_config.CeleryMonitoringAppConfig',
    'corehq.form_processor.app_config.FormProcessorAppConfig',
    'corehq.sql_db.app_config.SqlDbAppConfig',
    'corehq.sql_accessors',
    'corehq.sql_proxy_accessors',
    'corehq.sql_proxy_standby_accessors',
    'corehq.pillows',
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
    'corehq.apps.app_manager.AppManagerAppConfig',
    'corehq.apps.es.app_config.ElasticAppConfig',
    'corehq.apps.fixtures',
    'corehq.apps.case_importer',
    'corehq.apps.reminders',
    'corehq.apps.translations',
    'corehq.apps.user_importer',
    'corehq.apps.users',
    'corehq.apps.settings',
    'corehq.apps.ota',
    'corehq.apps.groups',
    'corehq.apps.mobile_auth',
    'corehq.apps.sms',
    'corehq.apps.email',
    'corehq.apps.events',
    'corehq.apps.geospatial',
    'corehq.apps.smsforms',
    'corehq.apps.sso',
    'corehq.apps.ivr',
    'corehq.apps.oauth_integrations',
    'corehq.messaging.MessagingAppConfig',
    'corehq.messaging.scheduling',
    'corehq.messaging.scheduling.scheduling_partitioned',
    'corehq.messaging.smsbackends.tropo',
    'corehq.messaging.smsbackends.turn',
    'corehq.messaging.smsbackends.twilio',
    'corehq.messaging.smsbackends.infobip',
    'corehq.messaging.smsbackends.amazon_pinpoint',
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
    'corehq.messaging.smsbackends.trumpia',
    'corehq.messaging.smsbackends.apposit',
    'corehq.messaging.smsbackends.test',
    'corehq.apps.registration',
    'corehq.messaging.smsbackends.unicel',
    'corehq.messaging.smsbackends.vertex',
    'corehq.messaging.smsbackends.start_enterprise',
    'corehq.messaging.smsbackends.ivory_coast_mtn',
    'corehq.messaging.smsbackends.airtel_tcl',
    'corehq.apps.reports.app_config.ReportsModule',
    'corehq.apps.reports_core',
    'corehq.apps.saved_reports',
    'corehq.apps.userreports.app_config.UserReports',
    'corehq.apps.aggregate_ucrs',
    'corehq.apps.data_interfaces.app_config.DataInterfacesAppConfig',
    'corehq.apps.export',
    'corehq.apps.builds',
    'corehq.apps.api',
    'corehq.apps.notifications',
    'corehq.apps.cachehq',
    'corehq.apps.toggle_ui',
    'corehq.couchapps',
    'corehq.preindex',
    'corehq.tabs',
    'soil',
    'phonelog',
    'pillowtop',
    'pillow_retry',
    'corehq.apps.styleguide',
    'corehq.messaging.smsbackends.grapevine',
    'corehq.apps.dashboard',
    'corehq.motech',
    'corehq.motech.dhis2',
    'corehq.motech.fhir',
    'corehq.motech.openmrs',
    'corehq.motech.repeaters',
    'corehq.motech.generic_inbound',
    'corehq.toggles',
    'corehq.util',
    'dimagi.ext',
    'corehq.blobs',
    'corehq.apps.case_search',
    'corehq.apps.zapier.apps.ZapierConfig',
    'corehq.apps.translations',

    # custom reports
    'custom.reports.mc',
    'custom.ucla',

    'custom.up_nrhm',

    'custom.common',

    'custom.hki',
    'custom.champ',
    'custom.covid',
    'custom.inddex',
    'custom.onse',
    'custom.nutrition_project',
    'custom.cowin.COWINAppConfig',
    'custom.hmhb',

    'custom.ccqa',

    'corehq.extensions.app_config.ExtensionAppConfig',  # this should be last in the list
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
    '/a/{domain}/settings/project/billing/statements/',
    '/a/{domain}/settings/project/billing_information/',
    '/a/{domain}/settings/project/flags/',
    '/a/{domain}/settings/project/internal/calculations/',
    '/a/{domain}/settings/project/internal/info/',
    '/a/{domain}/settings/project/internal_subscription_management/',
    '/a/{domain}/settings/project/project_limits/',
    '/a/{domain}/settings/project/subscription/',
)

####### Release Manager App settings  #######
RELEASE_FILE_PATH = os.path.join("data", "builds")

## soil heartbead config ##
SOIL_HEARTBEAT_CACHE_KEY = "django-soil-heartbeat"


####### Shared/Global/UI Settings #######

# restyle some templates
BASE_TEMPLATE = "hqwebapp/bootstrap3/base_navigation.html"
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

# the physical server emailing - differentiate if needed
SERVER_EMAIL = 'commcarehq-noreply@example.com'
DEFAULT_FROM_EMAIL = 'commcarehq-noreply@example.com'
SUPPORT_EMAIL = "support@example.com"
SAAS_OPS_EMAIL = "saas-ops@example.com"
PROBONO_SUPPORT_EMAIL = 'pro-bono@example.com'
ACCOUNTS_EMAIL = 'accounts@example.com'
DATA_EMAIL = 'datatree@example.com'
SUBSCRIPTION_CHANGE_EMAIL = 'accounts+subchange@example.com'
INTERNAL_SUBSCRIPTION_CHANGE_EMAIL = 'accounts+subchange+internal@example.com'
BILLING_EMAIL = 'billing-comm@example.com'
INVOICING_CONTACT_EMAIL = 'accounts@example.com'
GROWTH_EMAIL = 'growth@example.com'
MASTER_LIST_EMAIL = 'master-list@example.com'
SALES_EMAIL = 'sales@example.com'
EULA_CHANGE_EMAIL = 'eula-notifications@example.com'
PRIVACY_EMAIL = 'privacy@example.com'
CONTACT_EMAIL = 'info@example.com'
FEEDBACK_EMAIL = 'feedback@example.com'
BOOKKEEPER_CONTACT_EMAILS = []
SOFT_ASSERT_EMAIL = 'commcarehq-ops+soft_asserts@example.com'
DAILY_DEPLOY_EMAIL = None
EMAIL_SUBJECT_PREFIX = '[commcarehq] '
SAAS_REPORTING_EMAIL = None

# Return-Path is the email used to forward BOUNCE & COMPLAINT notifications
# This email must be a REAL email address, not a mailing list, otherwise
# the emails from mailer daemon will be swallowed up by spam filters.
RETURN_PATH_EMAIL = None

# This will trigger a periodic task to check the RETURN_PATH_EMAIL inbox for
# SES bounce and complaint notifications.
RETURN_PATH_EMAIL_PASSWORD = None

# Allows reception of SES Events to the log_email_event endpoint to update
# MessagingSubEvent status This configuration set should be set up for each
# environment here:
# https://console.aws.amazon.com/ses/home?region=us-east-1#configuration-set-list:

SES_CONFIGURATION_SET = None
SNS_EMAIL_EVENT_SECRET = None

ENABLE_SOFT_ASSERT_EMAILS = True
IS_DIMAGI_ENVIRONMENT = True

LOCAL_SERVER_ENVIRONMENT = 'localdev'
SERVER_ENVIRONMENT = LOCAL_SERVER_ENVIRONMENT
ICDS_ENVS = ('icds',)
# environments located in india, this should not even include staging
INDIAN_ENVIRONMENTS = ('india', 'icds-cas', 'icds-staging')
UNLIMITED_RULE_RESTART_ENVS = ('echis', 'pna', 'swiss')

# minimum minutes between updates to user reporting metadata
USER_REPORTING_METADATA_UPDATE_FREQUENCY = 15
USER_REPORTING_METADATA_BATCH_ENABLED = False
USER_REPORTING_METADATA_BATCH_SCHEDULE = {'timedelta': {'minutes': 5}}


BASE_ADDRESS = 'localhost:8000'

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
    "corehq.apps.locations.fixtures.location_fixture_generator",
    "corehq.apps.locations.fixtures.flat_location_fixture_generator",
    "corehq.apps.registry.fixtures.registry_fixture_generator",
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
CELERY_REMINDER_CASE_UPDATE_BULK_QUEUE = 'reminder_rule_queue'  # override in localsettings
CELERY_REPEAT_RECORD_QUEUE = 'repeat_record_queue'
CELERY_LOCATION_REASSIGNMENT_QUEUE = 'celery'

# Will cause a celery task to raise a SoftTimeLimitExceeded exception if
# time limit is exceeded.
CELERY_TASK_SOFT_TIME_LIMIT = 86400 * 2  # 2 days in seconds

# http://docs.celeryproject.org/en/3.1/configuration.html#celery-event-queue-ttl
# Keep messages in the events queue only for 2 hours
CELERY_EVENT_QUEUE_TTL = 2 * 60 * 60

# Default serializer should be changed back to 'json' after
# https://github.com/celery/celery/issues/6759 is fixed
CELERY_TASK_SERIALIZER = 'pickle'  # this value is ignored in commcare hq code, which will continue to default to json. it is used only for the celery inspect module". See corehq.apps.celery.shared_task
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
    "logistics_background_queue": None,
    "logistics_reminder_queue": None,
    "malt_generation_queue": 6 * 60 * 60,
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

# Used by the new reminders framework
LOCAL_AVAILABLE_CUSTOM_SCHEDULING_CONTENT = {}
AVAILABLE_CUSTOM_SCHEDULING_CONTENT = {
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
LOCAL_AVAILABLE_CUSTOM_REMINDER_RECIPIENTS = {}
AVAILABLE_CUSTOM_REMINDER_RECIPIENTS = {
    'HOST_CASE_OWNER_LOCATION':
        ['corehq.apps.reminders.custom_recipients.host_case_owner_location',
         "Custom: Extension Case -> Host Case -> Owner (which is a location)"],
    'HOST_CASE_OWNER_LOCATION_PARENT':
        ['corehq.apps.reminders.custom_recipients.host_case_owner_location_parent',
         "Custom: Extension Case -> Host Case -> Owner (which is a location) -> Parent location"],
    'MOBILE_WORKER_CASE_OWNER_LOCATION_PARENT':
        ['custom.abt.messaging.custom_recipients.abt_mobile_worker_case_owner_location_parent_old_framework',
         "Abt: The case owner's location's parent location"],
    'LOCATION_CASE_OWNER_PARENT_LOCATION':
        ['custom.abt.messaging.custom_recipients.abt_location_case_owner_parent_location_old_framework',
         "Abt: The case owner location's parent location"],
}


# Used by the new reminders framework
LOCAL_AVAILABLE_CUSTOM_SCHEDULING_RECIPIENTS = {}
AVAILABLE_CUSTOM_SCHEDULING_RECIPIENTS = {
    'HOST_CASE_OWNER_LOCATION':
        ['corehq.messaging.scheduling.custom_recipients.host_case_owner_location',
         "Custom: Extension Case -> Host Case -> Owner (which is a location)"],
    'HOST_CASE_OWNER_LOCATION_PARENT':
        ['corehq.messaging.scheduling.custom_recipients.host_case_owner_location_parent',
         "Custom: Extension Case -> Host Case -> Owner (which is a location) -> Parent location"],
    'MOBILE_WORKER_CASE_OWNER_LOCATION_PARENT':
        ['custom.abt.messaging.custom_recipients.abt_mobile_worker_case_owner_location_parent_new_framework',
         "Abt: The case owner's location's parent location"],
    'LOCATION_CASE_OWNER_PARENT_LOCATION':
        ['custom.abt.messaging.custom_recipients.abt_location_case_owner_parent_location_new_framework',
         "Abt: The case owner location's parent location"],
}

LOCAL_AVAILABLE_CUSTOM_RULE_CRITERIA = {}
AVAILABLE_CUSTOM_RULE_CRITERIA = {
    'COVID_US_ASSOCIATED_USER_CASES': 'custom.covid.rules.custom_criteria.associated_usercase_closed'
}

LOCAL_AVAILABLE_CUSTOM_RULE_ACTIONS = {}
AVAILABLE_CUSTOM_RULE_ACTIONS = {
    'COVID_US_CLOSE_CASES_ASSIGNED_CHECKIN': 'custom.covid.rules.custom_actions.close_cases_assigned_to_checkin',
    'COVID_US_SET_ACTIVITY_COMPLETE_TODAY':
        'custom.covid.rules.custom_actions.set_all_activity_complete_date_to_today',
    'GCC_SANGATH_SANITIZE_SESSIONS_PEER_RATING':
        'custom.gcc_sangath.rules.custom_actions.sanitize_session_peer_rating',
    'DFCI_SWASTH_UPDATE_COUNSELLOR_LOAD': 'custom.dfci_swasth.rules.custom_actions.update_counsellor_load',
}

####### auditcare parameters #######
AUDIT_ALL_VIEWS = False
AUDIT_VIEWS = []
AUDIT_MODULES = []
AUDIT_ADMIN_VIEWS = False

# Don't use google analytics unless overridden in localsettings
ANALYTICS_IDS = {
    'GOOGLE_ANALYTICS_API_ID': '',
    'KISSMETRICS_KEY': '',
    'HUBSPOT_ACCESS_TOKEN': '',
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

MAPBOX_ACCESS_TOKEN = ''

OPEN_EXCHANGE_RATES_API_ID = ''

# import local settings if we find them
LOCAL_APPS = ()
LOCAL_MIDDLEWARE = ()
LOCAL_PILLOWTOPS = {}

RUN_FORM_META_PILLOW = True
RUN_CASE_SEARCH_PILLOW = True
RUN_UNKNOWN_USER_PILLOW = True
RUN_DEDUPLICATION_PILLOW = True

# Repeaters in the order in which they should appear in "Data Forwarding"
REPEATER_CLASSES = [
    'corehq.motech.repeaters.models.FormRepeater',
    'corehq.motech.repeaters.models.CaseRepeater',
    'corehq.motech.repeaters.models.CreateCaseRepeater',
    'corehq.motech.repeaters.models.UpdateCaseRepeater',
    'corehq.motech.repeaters.models.ReferCaseRepeater',
    'corehq.motech.repeaters.models.DataRegistryCaseUpdateRepeater',
    'corehq.motech.repeaters.models.ShortFormRepeater',
    'corehq.motech.repeaters.models.AppStructureRepeater',
    'corehq.motech.repeaters.models.UserRepeater',
    'corehq.motech.repeaters.models.LocationRepeater',
    'corehq.motech.fhir.repeaters.FHIRRepeater',
    'corehq.motech.openmrs.repeaters.OpenmrsRepeater',
    'corehq.motech.dhis2.repeaters.Dhis2Repeater',
    'corehq.motech.dhis2.repeaters.Dhis2EntityRepeater',
    'custom.cowin.repeaters.BeneficiaryRegistrationRepeater',
    'custom.cowin.repeaters.BeneficiaryVaccinationRepeater',
    'corehq.motech.repeaters.expression.repeaters.CaseExpressionRepeater',
]

# Override this in localsettings to add new repeater types
LOCAL_REPEATER_CLASSES = []

# tuple of fully qualified repeater class names that are enabled.
# Set to None to enable all or empty tuple to disable all.
# This will not prevent users from creating
REPEATERS_WHITELIST = None

# how many tasks to split the check_repeaters process into
CHECK_REPEATERS_PARTITION_COUNT = 1

# If ENABLE_PRELOGIN_SITE is set to true, redirect to Dimagi.com urls
ENABLE_PRELOGIN_SITE = False

# dimagi.com urls
PRICING_PAGE_URL = "https://www.dimagi.com/commcare/pricing/"

# Sumologic log aggregator
SUMOLOGIC_URL = None

# on both a single instance or distributed setup this should assume localhost
ELASTICSEARCH_HOST = 'localhost'
ELASTICSEARCH_PORT = 9200
ELASTICSEARCH_MAJOR_VERSION = 2
# If elasticsearch queries take more than this, they result in timeout errors
ES_SEARCH_TIMEOUT = 30

# The variables should be used while reindexing an index.
# When the variables are set to true the data will be written to both primary and secondary indexes.

ES_APPS_INDEX_MULTIPLEXED = True
ES_CASE_SEARCH_INDEX_MULTIPLEXED = True
ES_CASES_INDEX_MULTIPLEXED = True
ES_DOMAINS_INDEX_MULTIPLEXED = True
ES_FORMS_INDEX_MULTIPLEXED = True
ES_GROUPS_INDEX_MULTIPLEXED = True
ES_SMS_INDEX_MULTIPLEXED = True
ES_USERS_INDEX_MULTIPLEXED = True


# Setting the variable to True would mean that the primary index would become secondary and vice-versa
# This should only be set to True after successfully running and verifying migration command on a particular index. 
ES_APPS_INDEX_SWAPPED = False
ES_CASE_SEARCH_INDEX_SWAPPED = False
ES_CASES_INDEX_SWAPPED = False
ES_DOMAINS_INDEX_SWAPPED = False
ES_FORMS_INDEX_SWAPPED = False
ES_GROUPS_INDEX_SWAPPED = False
ES_SMS_INDEX_SWAPPED = False
ES_USERS_INDEX_SWAPPED = False

BITLY_OAUTH_TOKEN = None

OAUTH2_PROVIDER_ACCESS_TOKEN_MODEL = 'oauth2_provider.AccessToken'
OAUTH2_PROVIDER_APPLICATION_MODEL = 'oauth2_provider.Application'


def _pkce_required(client_id):
    from corehq.apps.hqwebapp.models import pkce_required
    return pkce_required(client_id)


OAUTH2_PROVIDER = {
    # until we have clearer project-level checks on this, just expire the token every
    # 15 minutes to match HIPAA constraints.
    # https://django-oauth-toolkit.readthedocs.io/en/latest/settings.html#access-token-expire-seconds
    'ACCESS_TOKEN_EXPIRE_SECONDS': 15 * 60,
    'PKCE_REQUIRED': _pkce_required,
    'SCOPES': {
        'access_apis': 'Access API data on all your CommCare projects',
        'reports:view': 'Allow users to view and download all report data',
        'mobile_access': 'Allow access to mobile sync and submit endpoints',
        'sync': '(Deprecated, do not use) Allow access to mobile endpoints',
    },
    'REFRESH_TOKEN_EXPIRE_SECONDS': 60 * 60 * 24 * 15,  # 15 days
}


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
COMPRESS_PRECOMPILERS = AVAILABLE_COMPRESS_PRECOMPILERS = (
    ('text/less', 'corehq.apps.hqwebapp.precompilers.LessFilter'),
    ('text/scss', 'corehq.apps.hqwebapp.precompilers.SassFilter'),
)
# if not overwritten in localsettings, these will be replaced by the value they return
# using the local DEBUG value (which we don't have access to here yet)
COMPRESS_ENABLED = lambda: not DEBUG and not UNIT_TESTING  # noqa: E731
COMPRESS_OFFLINE = lambda: not DEBUG and not UNIT_TESTING  # noqa: E731
COMPRESS_FILTERS = {
    'css': [
        'compressor.filters.css_default.CssAbsoluteFilter',
        'compressor.filters.cssmin.rCSSMinFilter',
    ],
    'js': [
        'compressor.filters.jsmin.rJSMinFilter',
    ],
}

LESS_B3_PATHS = {
    'variables': '../../../hqwebapp/less/_hq/includes/variables',
    'mixins': '../../../hqwebapp/less/_hq/includes/mixins',
}

BOOTSTRAP_MIGRATION_LOGS_DIR = None

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

# List of metrics providers to use. Available providers:
# * 'corehq.util.metrics.datadog.DatadogMetrics'
# * 'corehq.util.metrics.prometheus.PrometheusMetrics'
METRICS_PROVIDERS = []

DATADOG_API_KEY = None
DATADOG_APP_KEY = None

SYNCLOGS_SQL_DB_ALIAS = 'default'

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

KAFKA_BROKERS = ['localhost:9092']
KAFKA_API_VERSION = None

MOBILE_INTEGRATION_TEST_TOKEN = None

COMMCARE_HQ_NAME = {
    "default": "CommCare HQ",
}
COMMCARE_NAME = {
    "default": "CommCare",
}

ALLOW_MAKE_SUPERUSER_COMMAND = True

ENTERPRISE_MODE = False

RESTRICT_DOMAIN_CREATION = False

CUSTOM_LANDING_PAGE = False

SENTRY_DSN = None
SENTRY_REPOSITORY = 'dimagi/commcare-hq'
SENTRY_ORGANIZATION_SLUG = 'dimagi'
SENTRY_PROJECT_SLUG = 'commcarehq'

# used for creating releases and deploys
SENTRY_API_KEY = None

DATA_UPLOAD_MAX_MEMORY_SIZE = None

# 10MB max upload size - applied to specific views
# consider migrating to `DATA_UPLOAD_MAX_MEMORY_SIZE` which is universally applied
MAX_UPLOAD_SIZE = 10 * 1024 * 1024

# Size limit on attachment other than the xml form.
MAX_UPLOAD_SIZE_ATTACHMENT = 15 * 1024 * 1024

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

MAX_RULE_UPDATES_IN_ONE_RUN = 10000
RULE_UPDATE_HOUR = 0

DEFAULT_ODATA_FEED_LIMIT = 25

# used for providing separate landing pages for different URLs
# default will be used if no hosts match
CUSTOM_LANDING_TEMPLATE = {
    # "default": 'login_and_password/login.html',
}

# used to override low-level index settings (number_of_replicas, number_of_shards, etc)
ES_SETTINGS = None

PHI_API_KEY = None
PHI_PASSWORD = None

STATIC_DATA_SOURCE_PROVIDERS = [
    'corehq.apps.callcenter.data_source.call_center_data_source_configuration_provider'
]

BYPASS_SESSIONS_FOR_MOBILE = False

SESSION_BYPASS_URLS = [
    r'^/a/{domain}/receiver/',
    r'^/a/{domain}/phone/restore/',
    r'^/a/{domain}/phone/search/',
    r'^/a/{domain}/phone/claim-case/',
    r'^/a/{domain}/phone/heartbeat/',
    r'^/a/{domain}/phone/keys/',
    r'^/a/{domain}/phone/admin_keys/',
    r'^/a/{domain}/apps/download/',
]

# Disable builtin throttling for two factor backup tokens, since we have our own
# See corehq.apps.hqwebapp.signals and corehq.apps.hqwebapp.forms for details
OTP_STATIC_THROTTLE_FACTOR = 0
# Adding OTP_TOTP_THROTTLE_FACTOR and TWO_FACTOR_PHONE_THROTTLE_FACTOR to preserve behavior after upgrading
# past version 1.15.4 of django-two-factor-auth, which changed the factor to 10.
OTP_TOTP_THROTTLE_FACTOR = 1
TWO_FACTOR_PHONE_THROTTLE_FACTOR = 1

ALLOW_PHONE_AS_DEFAULT_TWO_FACTOR_DEVICE = False
RATE_LIMIT_SUBMISSIONS = False

DATA_UPLOAD_MAX_NUMBER_FILES = None

# If set to a positive number, exports requested more than this many seconds ago
# without the email option will be quickly rejected.
# This is useful for load-shedding in times of crisis.
STALE_EXPORT_THRESHOLD = None

REQUIRE_TWO_FACTOR_FOR_SUPERUSERS = False

LOCAL_CUSTOM_DB_ROUTING = {}

DEFAULT_COMMCARE_EXTENSIONS = [
    "custom.abt.commcare_extensions",
    "custom.eqa.commcare_extensions",
    "mvp.commcare_extensions",
    "custom.nutrition_project.commcare_extensions",
    "custom.samveg.commcare_extensions",
]
COMMCARE_EXTENSIONS = []

IGNORE_ALL_DEMO_USER_SUBMISSIONS = False

# to help in performance, avoid use of phone entries in an environment that does not need them
# so HQ does not try to keep them up to date
USE_PHONE_ENTRIES = True
COMMCARE_ANALYTICS_HOST = ""

# FCM Server creds used for sending FCM Push Notifications
FCM_CREDS = None

CONNECTID_USERINFO_URL = 'http://localhost:8080/o/userinfo'

MAX_MOBILE_UCR_LIMIT = 300  # used in corehq.apps.cloudcare.util.should_restrict_web_apps_usage

# used by periodic tasks that delete soft deleted data older than PERMANENT_DELETION_WINDOW days
PERMANENT_DELETION_WINDOW = 30  # days

# GSheets related work that was dropped, but should be picked up in the near future
GOOGLE_OATH_CONFIG = {}
GOOGLE_OAUTH_SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
GOOGLE_SHEETS_API_NAME = "sheets"
GOOGLE_SHEETS_API_VERSION = "v4"
DAYS_KEEP_GSHEET_STATUS = 14

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
    if str(error) != "No module named 'localsettings'":
        raise error
    # fallback in case nothing else is found - used for readthedocs
    from dev_settings import *


AVAILABLE_CUSTOM_SCHEDULING_CONTENT.update(LOCAL_AVAILABLE_CUSTOM_SCHEDULING_CONTENT)
AVAILABLE_CUSTOM_REMINDER_RECIPIENTS.update(LOCAL_AVAILABLE_CUSTOM_REMINDER_RECIPIENTS)
AVAILABLE_CUSTOM_SCHEDULING_RECIPIENTS.update(LOCAL_AVAILABLE_CUSTOM_SCHEDULING_RECIPIENTS)
AVAILABLE_CUSTOM_RULE_CRITERIA.update(LOCAL_AVAILABLE_CUSTOM_RULE_CRITERIA)
AVAILABLE_CUSTOM_RULE_ACTIONS.update(LOCAL_AVAILABLE_CUSTOM_RULE_ACTIONS)

REPEATER_CLASSES.extend(LOCAL_REPEATER_CLASSES)

COMMCARE_EXTENSIONS.extend(DEFAULT_COMMCARE_EXTENSIONS)

# The defaults above are given as a function of (or rather a closure on) DEBUG,
# so if not overridden they need to be evaluated after DEBUG is set
if callable(COMPRESS_ENABLED):
    COMPRESS_ENABLED = COMPRESS_ENABLED()
if callable(COMPRESS_OFFLINE):
    COMPRESS_OFFLINE = COMPRESS_OFFLINE()

# These default values can't be overridden.
# Should you someday need to do so, use the lambda/if callable pattern above
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = SECURE_COOKIES = not DEBUG
SESSION_COOKIE_HTTPONLY = CSRF_COOKIE_HTTPONLY = True

# This is commented because it is not required now. We don't need to instrument all the services rn on staging.
# The below lines can be uncommented when we need to turn on app level tracing on any env.
# if SERVER_ENVIRONMENT == 'staging':
#     from ddtrace import patch_all
#     patch_all()


if UNIT_TESTING:
    # COMPRESS_COMPILERS overrides COMPRESS_ENABLED = False, so must be
    # cleared to disable compression completely. CSS/less compression is
    # very slow and should especially be avoided in tests. Tests that
    # need to test compression should use
    # @override_settings(
    #     COMPRESS_ENABLED=True,
    #     COMPRESS_PRECOMPILERS=settings.AVAILABLE_COMPRESS_PRECOMPILERS,
    # )
    COMPRESS_PRECOMPILERS = ()


# Unless DISABLE_SERVER_SIDE_CURSORS has explicitly been set, default to True because Django >= 1.11.1 and our
# hosting environments use pgBouncer with transaction pooling. For more information, see:
# https://docs.djangoproject.com/en/1.11/releases/1.11.1/#allowed-disabling-server-side-cursors-on-postgresql
for database in DATABASES.values():
    if (
        database['ENGINE'] == 'django.db.backends.postgresql' and
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
                'corehq.util.context_processors.subscription_banners',
                'corehq.util.context_processors.js_api_keys',
                'corehq.util.context_processors.js_toggles',
                'corehq.util.context_processors.websockets_override',
                'corehq.util.context_processors.commcare_hq_names',
                'corehq.util.context_processors.emails',
                'corehq.util.context_processors.status_page',
                'corehq.util.context_processors.sentry',
                'corehq.util.context_processors.bootstrap5',
                'corehq.util.context_processors.js_privileges',
            ],
            'debug': DEBUG,
            'loaders': [
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
            ],
        },
    },
]

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
        },
        'simple': {
            'format': '%(asctime)s %(levelname)s [%(name)s] %(message)s'
        },
        'pillowtop': {
            'format': '%(asctime)s %(levelname)s %(module)s %(message)s'
        },
        'couch-request-formatter': {
            'format': '%(asctime)s [%(username)s:%(domain)s] %(hq_url)s %(task_name)s %(database)s %(method)s %(status_code)s %(content_length)s %(path)s %(duration)s'
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
        'kafka_audit': {
            'format': '%(asctime)s,%(message)s'
        },
    },
    'filters': {
        'hqrequest': {
            '()': 'corehq.util.log.HQRequestFilter',
        },
        'celerytask': {
            '()': 'corehq.util.log.CeleryTaskFilter',
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
            'filters': ['hqrequest', 'celerytask'],
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
        'null': {
            'class': 'logging.NullHandler',
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
            'handlers': ['file'],
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
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': True,
        },
        'celery.task': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False
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
            'handlers': ['accountinglog', 'console'],
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
        'commcare_auth': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False,
        }
    }
}

if LOCAL_LOGGING_CONFIG:
    for key, config in LOCAL_LOGGING_CONFIG.items():
        if key in ('handlers', 'loggers', 'formatters', 'filters'):
            LOGGING[key].update(config)
        else:
            LOGGING[key] = config

fix_logger_obfuscation_ = globals().get("FIX_LOGGER_ERROR_OBFUSCATION")
helper.fix_logger_obfuscation(fix_logger_obfuscation_, LOGGING)

if DEBUG:
    INSTALLED_APPS = INSTALLED_APPS + ('corehq.apps.mocha',)
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

# Mapping of app_label to DB name or reporting DB alias (see REPORTING_DATABASES)
CUSTOM_DB_ROUTING = {}
CUSTOM_DB_ROUTING.update(LOCAL_CUSTOM_DB_ROUTING)

INDICATOR_CONFIG = {
}

COMPRESS_URL = STATIC_CDN + STATIC_URL

# Couch database name suffixes
USERS_GROUPS_DB = 'users'
DOMAINS_DB = 'domains'
APPS_DB = 'apps'
META_DB = 'meta'

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
    'grapevine',

    # custom reports
    'accounting',
    ('repeaters', 'receiverwrapper'),
    ('userreports', META_DB),
    ('custom_data_fields', META_DB),
    ('export', META_DB),
    ('callcenter', META_DB),

    # users and groups
    ('groups', USERS_GROUPS_DB),
    ('users', USERS_GROUPS_DB),

    # domains
    ('domain', DOMAINS_DB),

    # applications
    ('app_manager', APPS_DB),
]

COUCH_SETTINGS_HELPER = helper.CouchSettingsHelper(
    COUCH_DATABASES,
    COUCHDB_APPS,
    [USERS_GROUPS_DB, DOMAINS_DB, APPS_DB],
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

WEB_USER_TERM = "Web User"

DEFAULT_CURRENCY = "USD"
DEFAULT_CURRENCY_SYMBOL = "$"

SMS_HANDLERS = [
    'corehq.apps.commtrack.sms.handle',
    'corehq.apps.sms.handlers.keyword.sms_keyword_handler',
    'corehq.apps.sms.handlers.form_session.form_session_handler',
    'corehq.apps.sms.handlers.fallback.fallback_handler',
]


SMS_LOADED_SQL_BACKENDS = [
    'corehq.messaging.smsbackends.apposit.models.SQLAppositBackend',
    'corehq.messaging.smsbackends.grapevine.models.SQLGrapevineBackend',
    'corehq.messaging.smsbackends.http.models.SQLHttpBackend',
    'corehq.messaging.smsbackends.mach.models.SQLMachBackend',
    'corehq.messaging.smsbackends.megamobile.models.SQLMegamobileBackend',
    'corehq.messaging.smsbackends.push.models.PushBackend',
    'corehq.messaging.smsbackends.starfish.models.StarfishBackend',
    'corehq.messaging.smsbackends.trumpia.models.TrumpiaBackend',
    'corehq.messaging.smsbackends.sislog.models.SQLSislogBackend',
    'corehq.messaging.smsbackends.smsgh.models.SQLSMSGHBackend',
    'corehq.messaging.smsbackends.telerivet.models.SQLTelerivetBackend',
    'corehq.messaging.smsbackends.test.models.SQLTestSMSBackend',
    'corehq.messaging.smsbackends.tropo.models.SQLTropoBackend',
    'corehq.messaging.smsbackends.turn.models.SQLTurnWhatsAppBackend',
    'corehq.messaging.smsbackends.twilio.models.SQLTwilioBackend',
    'corehq.messaging.smsbackends.infobip.models.InfobipBackend',
    'corehq.messaging.smsbackends.amazon_pinpoint.models.PinpointBackend',
    'corehq.messaging.smsbackends.unicel.models.SQLUnicelBackend',
    'corehq.messaging.smsbackends.yo.models.SQLYoBackend',
    'corehq.messaging.smsbackends.vertex.models.VertexBackend',
    'corehq.messaging.smsbackends.start_enterprise.models.StartEnterpriseBackend',
    'corehq.messaging.smsbackends.ivory_coast_mtn.models.IvoryCoastMTNBackend',
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

# These are custom templates which can wrap default the sms/chat.html template
CUSTOM_CHAT_TEMPLATES = {}

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
            'name': 'UnknownUsersPillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.pillows.user.get_unknown_users_pillow',
        },
        {
            'name': 'case_messaging_sync_pillow',
            'class': 'pillowtop.pillow.interface.ConstructedPillow',
            'instance': 'corehq.messaging.pillow.get_case_messaging_sync_pillow',
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

STATIC_UCR_REPORTS = [
    os.path.join('custom', '_legacy', 'mvp', 'ucr', 'reports', 'deidentified_va_report.json'),
    os.path.join('custom', 'abt', 'reports', 'incident_report.json'),
    os.path.join('custom', 'abt', 'reports', 'sms_indicator_report.json'),
    os.path.join('custom', 'abt', 'reports', 'spray_progress_country.json'),
    os.path.join('custom', 'abt', 'reports', 'spray_progress_level_1.json'),
    os.path.join('custom', 'abt', 'reports', 'spray_progress_level_2.json'),
    os.path.join('custom', 'abt', 'reports', 'spray_progress_level_3.json'),
    os.path.join('custom', 'abt', 'reports', 'spray_progress_level_4.json'),
    os.path.join('custom', 'abt', 'reports', 'supervisory_report_v2019.json'),
    os.path.join('custom', 'abt', 'reports', 'supervisory_report_v2020.json'),
    os.path.join('custom', 'echis_reports', 'ucr', 'reports', '*.json'),
    os.path.join('custom', 'ccqa', 'ucr', 'reports', 'patients.json'),  # For testing static UCRs
]


STATIC_DATA_SOURCES = [
    os.path.join('custom', 'up_nrhm', 'data_sources', 'location_hierarchy.json'),
    os.path.join('custom', 'up_nrhm', 'data_sources', 'asha_facilitators.json'),
    os.path.join('custom', 'abt', 'reports', 'data_sources', 'sms_case.json'),
    os.path.join('custom', 'abt', 'reports', 'data_sources', 'supervisory.json'),
    os.path.join('custom', 'abt', 'reports', 'data_sources', 'supervisory_v2.json'),
    os.path.join('custom', 'abt', 'reports', 'data_sources', 'supervisory_v2019.json'),
    os.path.join('custom', 'abt', 'reports', 'data_sources', 'supervisory_v2020.json'),
    os.path.join('custom', 'abt', 'reports', 'data_sources', 'late_pmt.json'),
    os.path.join('custom', '_legacy', 'mvp', 'ucr', 'reports', 'data_sources', 'va_datasource.json'),
    os.path.join('custom', 'reports', 'mc', 'data_sources', 'malaria_consortium.json'),
    os.path.join('custom', 'reports', 'mc', 'data_sources', 'weekly_forms.json'),
    os.path.join('custom', 'champ', 'ucr_data_sources', 'champ_cameroon.json'),
    os.path.join('custom', 'champ', 'ucr_data_sources', 'enhanced_peer_mobilization.json'),
    os.path.join('custom', 'inddex', 'ucr', 'data_sources', '*.json'),

    os.path.join('custom', 'echis_reports', 'ucr', 'data_sources', '*.json'),
    os.path.join('custom', 'polio_rdc', 'ucr', 'data_sources', 'users.json'),
    os.path.join('custom', 'ccqa', 'ucr', 'data_sources', 'patients.json'),  # For testing static UCRs
]

for k, v in LOCAL_PILLOWTOPS.items():
    plist = PILLOWTOPS.get(k, [])
    plist.extend(v)
    PILLOWTOPS[k] = plist

COUCH_CACHE_BACKENDS = [
    'corehq.apps.cachehq.cachemodels.ReportGenerationCache',
    'corehq.apps.cachehq.cachemodels.UserReportsDataSourceCache',
    'dimagi.utils.couch.cache.cache_core.gen.GlobalCache',
]

CUSTOM_UCR_EXPRESSIONS = [
    ('indexed_case', 'corehq.apps.userreports.expressions.extension_expressions.indexed_case_expression'),
    ('location_type_name', 'corehq.apps.locations.ucr_expressions.location_type_name'),
    ('location_parent_id', 'corehq.apps.locations.ucr_expressions.location_parent_id'),
    ('ancestor_location', 'corehq.apps.locations.ucr_expressions.ancestor_location'),
]

DOMAIN_MODULE_MAP = {
    'mc-inscale': 'custom.reports.mc',

    'up-nrhm': 'custom.up_nrhm',
    'nhm-af-up': 'custom.up_nrhm',
    'india-nutrition-project': 'custom.nutrition_project',

    'champ-cameroon': 'custom.champ',
    'onse-iss': 'custom.onse',

    # vectorlink domains
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
    'kenya-vca': 'custom.abt',
    'pmievolve-madagascar': 'custom.abt',
    'pmievolve-malawi': 'custom.abt',
    'pmievolve-mozambique': 'custom.abt',
    'pmievolve-rwanda': 'custom.abt',
    'pmievolve-zambia': 'custom.abt',
    'vectorlink-benin': 'custom.abt',
    'vectorlink-burkina-faso': 'custom.abt',
    'vectorlink-ethiopia': 'custom.abt',
    'vectorlink-ghana': 'custom.abt',
    'vectorlink-ivorycoast': 'custom.abt',
    'vectorlink-kenya': 'custom.abt',
    'vectorlink-madagascar': 'custom.abt',
    'vectorlink-malawi': 'custom.abt',
    'vectorlink-mali': 'custom.abt',
    'vectorlink-mozambique': 'custom.abt',
    'vectorlink-rwanda': 'custom.abt',
    'vectorlink-senegal': 'custom.abt',
    'vectorlink-sierra-leone': 'custom.abt',
    'vectorlink-tanzania': 'custom.abt',
    'vectorlink-uganda': 'custom.abt',
    'vectorlink-zambia': 'custom.abt',
    'vectorlink-zimbabwe': 'custom.abt',

    'inddex-reports': 'custom.inddex',
    'inddex-multilingual': 'custom.inddex',
    'inddex-multi-vn': 'custom.inddex',
    'iita-fcms-nigeria': 'custom.inddex',
    'cambodia-arch-3-study': 'custom.inddex',
    'senegal-arch-3-study': 'custom.inddex',
    'inddex24-dev': 'custom.inddex',

    'ccqa': 'custom.ccqa',
}

THROTTLE_SCHED_REPORTS_PATTERNS = (
    # Regex patterns matching domains whose scheduled reports use a
    # separate queue so that they don't hold up the background queue.
    'ews-ghana$',
    'mvp-',
)

#### Django Compressor Stuff after localsettings overrides ####

COMPRESS_OFFLINE_CONTEXT = {
    'base_template': BASE_TEMPLATE,
    'login_template': LOGIN_TEMPLATE,
    'original_template': BASE_ASYNC_TEMPLATE,
}

COMPRESS_CSS_HASHING_METHOD = 'content'


if 'locmem' not in CACHES:
    CACHES['locmem'] = {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}
if 'dummy' not in CACHES:
    CACHES['dummy'] = {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}


REST_FRAMEWORK = {
    'DATETIME_FORMAT': '%Y-%m-%dT%H:%M:%S.%fZ',
}

if not SENTRY_DSN:
    pub_key = globals().get('SENTRY_PUBLIC_KEY')
    priv_key = globals().get('SENTRY_PRIVATE_KEY')
    project_id = globals().get('SENTRY_PROJECT_ID')
    if pub_key and priv_key and project_id:
        SENTRY_DSN = 'https://{pub_key}:{priv_key}@sentry.io/{project_id}'.format(
            pub_key=pub_key,
            priv_key=priv_key,
            project_id=project_id
        )

        import warnings
        warnings.warn(inspect.cleandoc(f"""SENTRY configuration has changed

            Please replace SENTRY_PUBLIC_KEY, SENTRY_PRIVATE_KEY, SENTRY_PROJECT_ID with SENTRY_DSN:

            SENTRY_DSN = {SENTRY_DSN}

            The following settings are also recommended:
                SENTRY_ORGANIZATION_SLUG
                SENTRY_PROJECT_SLUG
                SENTRY_REPOSITORY

            SENTRY_QUERY_URL is not longer needed.
            """), DeprecationWarning)

COMMCARE_RELEASE = helper.get_release_name(BASE_DIR, SERVER_ENVIRONMENT)
if SENTRY_DSN:
    if 'SENTRY_QUERY_URL' not in globals():
        SENTRY_QUERY_URL = f'https://sentry.io/{SENTRY_ORGANIZATION_SLUG}/{SENTRY_PROJECT_SLUG}/?query='
    helper.configure_sentry(SERVER_ENVIRONMENT, SENTRY_DSN, COMMCARE_RELEASE)
    SENTRY_CONFIGURED = True
else:
    SENTRY_CONFIGURED = False

PACKAGE_MONITOR_REQUIREMENTS_FILE = os.path.join(FILEPATH, 'requirements', 'requirements.txt')

# Disable Datadog trace startup logs by default
# https://docs.datadoghq.com/tracing/troubleshooting/tracer_startup_logs/
os.environ['DD_TRACE_STARTUP_LOGS'] = os.environ.get('DD_TRACE_STARTUP_LOGS', 'False')

SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# NOTE: if you are adding a new setting that you intend to have other environments override,
# make sure you add it before localsettings are imported (from localsettings import *)
