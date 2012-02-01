#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

import os
import logging

CACHE_BACKEND = 'memcached://127.0.0.1:11211/'

DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = ()
MANAGERS = ADMINS


# default to the system's timezone settings
TIME_ZONE = "EST"


# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# Django i18n searches for translation files (django.po) within this dir
LOCALE_PATHS=['contrib/locale']

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = ''
STATIC_ROOT = ''

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = '/media/'
STATIC_URL = '/static/'

filepath = os.path.abspath(os.path.dirname(__file__))

STATICFILES_FINDERS = (
    "staticfiles.finders.FileSystemFinder",
    "staticfiles.finders.AppDirectoriesFinder"
)

STATICFILES_DIRS = (
    ('formdesigner', os.path.join(filepath,'submodules', 'formdesigner')),
)

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/media/'

# Make this unique, and don't share it with anybody.
SECRET_KEY = '2rgmwtyq$thj49+-6u7x9t39r7jflu&1ljj3x2c0n0fl$)04_0'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.load_template_source',
    'django.template.loaders.app_directories.load_template_source',
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
    'corehq.apps.domain.middleware.DomainMiddleware',
    'corehq.apps.users.middleware.UsersMiddleware',
    'auditcare.middleware.AuditMiddleware',
]

ROOT_URLCONF = "urls"

TEMPLATE_CONTEXT_PROCESSORS = [
    "django.core.context_processors.auth",
    "django.core.context_processors.debug",
    "django.core.context_processors.i18n",
    "django.core.context_processors.media",
    "django.core.context_processors.request",
    "django.contrib.messages.context_processors.messages",
    'staticfiles.context_processors.static',
    "corehq.util.context_processors.base_template", # sticks the base template inside all responses
    "corehq.util.context_processors.google_analytics",
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
    'staticfiles', #soon to be django.contrib.staticfiles in 1.3
    'south',
    'djcelery',    # pip install django-celery
    'djtables',    # pip install djtables
    #'ghettoq',     # pip install ghettoq
    'djkombu',     # pip install django-kombu
    'couchdbkit.ext.django',
)

HQ_APPS = (
    'django_digest',
    'django_rest_interface',
    'django_granular_permissions',
    'django_tables',
    'django_user_registration',
    'auditcare',
    'djangocouch',
    'djangocouchuser',
    'hqscripts',
    'casexml.apps.case',
    'casexml.apps.phone',
    'corehq.apps.cleanup',
    'corehq.apps.domain',
    'corehq.apps.domainsync',
    'corehq.apps.hqadmin',
    'corehq.apps.hqcase',
    'corehq.apps.hqwebapp',
    'corehq.apps.logtracker',
    'corehq.apps.docs',
    'corehq.apps.hqmedia',
    'couchforms',
    'couchexport',
    'couchlog',
    'formtranslate',
    'receiver',
    'langcodes',
    'corehq.apps.receiverwrapper',
    'corehq.apps.migration',
    'corehq.apps.app_manager',
    'corehq.apps.reminders',
    'corehq.apps.prescriptions',
    'corehq.apps.translations',
    'corehq.apps.users',
    'corehq.apps.ota',
    'corehq.apps.groups',
    'corehq.apps.sms',
    'corehq.apps.registration',
    'corehq.apps.unicel',
    'corehq.apps.reports',
    'corehq.apps.builds',
    'corehq.apps.api',
    'corehq.couchapps',
    'sofabed.forms',
    'soil',
    'corehq.apps.hqsofabed',
    'xep_hq_server',
    'touchforms.formplayer',
    'phonelog',
    'pathfinder',
    'hutch',
)

REFLEXIVE_URL_BASE = "localhost:8000"

INSTALLED_APPS = DEFAULT_APPS + HQ_APPS

TABS = [
    ("corehq.apps.reports.views.default", "Reports"),
    ("corehq.apps.app_manager.views.default", "Applications"),
    ("corehq.apps.sms.views.messaging", "Messages"),
    ("corehq.apps.users.views.users", "Users"),
    ("corehq.apps.domain.views.manage_domain", "My Domain"),
    ("corehq.apps.hqadmin.views.default", "Admin", "is_superuser"),
]

# after login, django redirects to this URL
# rather than the default 'accounts/profile'
LOGIN_REDIRECT_URL='/'


####### Domain settings  #######

DOMAIN_MAX_REGISTRATION_REQUESTS_PER_DAY=99
DOMAIN_SELECT_URL="/domain/select/"
LOGIN_URL="/accounts/login/"
# For the registration app
# One week to confirm a registered user account
ACCOUNT_ACTIVATION_DAYS=7 
# If a user tries to access domain admin pages but isn't a domain 
# administrator, here's where he/she is redirected
DOMAIN_NOT_ADMIN_REDIRECT_PAGE_NAME="homepage"

# domain syncs
# e.g. 
#               { sourcedomain1: { "domain": targetdomain1,
#                                  "transform": path.to.transformfunction1 },
#                 sourcedomain2: {...} }
DOMAIN_SYNCS = { }
# if you want to deidentify app names, put a dictionary in your settings
# of source names to deidentified names
DOMAIN_SYNC_APP_NAME_MAP = {}
DOMAIN_SYNC_DATABASE_NAME = "commcarehq-public"

####### Release Manager App settings  #######
RELEASE_FILE_PATH=os.path.join("data","builds")

## soil heartbead config ##
SOIL_HEARTBEAT_CACHE_KEY = "django-soil-heartbeat"


####### Shared/Global/UI Settings ######

# restyle some templates
BASE_TEMPLATE="hqwebapp/base.html"
LOGIN_TEMPLATE="login_and_password/login.html"
LOGGEDOUT_TEMPLATE="loggedout.html"

#logtracker settings variables
LOGTRACKER_ALERT_EMAILS = []
LOGTRACKER_LOG_THRESHOLD = 30
LOGTRACKER_ALERT_THRESHOLD = 40

# email settings: these ones are the custom hq ones
EMAIL_LOGIN="user@domain.com"
EMAIL_PASSWORD="changeme"
EMAIL_SMTP_HOST="smtp.gmail.com"
EMAIL_SMTP_PORT=587


PAGINATOR_OBJECTS_PER_PAGE = 15
PAGINATOR_MAX_PAGE_LINKS = 5

# OpenRosa Standards
OPENROSA_VERSION = "1.0"

# OTA restore fixture generators
FIXTURE_GENERATORS = ["corehq.apps.users.fixturegenerators.user_groups"]

# xep_hq_server settings
XEP_AUTHORIZE = 'corehq.apps.app_manager.models.authorize_xform_edit'
XEP_GET_XFORM = 'corehq.apps.app_manager.models.get_xform'
XEP_PUT_XFORM = 'corehq.apps.app_manager.models.put_xform'
GET_URL_BASE  = 'dimagi.utils.web.get_url_base'


DJANGO_LOG_FILE = "/var/log/commcarehq.django.log"
LOG_SIZE = 1000000
LOG_LEVEL   = "DEBUG"
LOG_FILE    = "/var/log/commcarehq.router.log"
LOG_FORMAT  = "[%(name)s]: %(message)s"
LOG_BACKUPS = 256 # number of logs to keep


SMS_GATEWAY_URL = "http://localhost:8001/"
SMS_GATEWAY_PARAMS = "user=my_username&password=my_password&id=%(phone_number)s&text=%(message)s"

# celery
CARROT_BACKEND = "django"


SKIP_SOUTH_TESTS = True
#AUTH_PROFILE_MODULE = 'users.HqUserProfile'
TEST_RUNNER = 'testrunner.HqTestSuiteRunner'
HQ_ACCOUNT_ROOT = "commcarehq.org" # this is what gets appended to @domain after your accounts

XFORMS_PLAYER_URL = "http://localhost:4444/"  # touchform's setting

# couchlog
SUPPORT_EMAIL = "commcarehq-support@dimagi.com"
COUCHLOG_BLUEPRINT_HOME = "%s%s" % (STATIC_URL, "hqwebapp/stylesheets/blueprint/")
COUCHLOG_DATATABLES_LOC = "%s%s" % (STATIC_URL, "hqwebapp/datatables/js/jquery.dataTables.min.js")
COUCHLOG_THRESHOLD = logging.WARNING

# couchlog/case search
LUCENE_ENABLED = False

# sofabed
FORMDATA_MODEL = 'hqsofabed.HQFormData'  

# unicel sms config
UNICEL_CONFIG = {"username": "Dimagi",
                 "password": "changeme",
                 "sender": "Promo" }


#auditcare parameters
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
GOOGLE_ANALYTICS_ID = ''

# import local settings if we find them
LOCAL_APPS = ()
LOCAL_MIDDLEWARE_CLASSES = ()
try:
    #try to see if there's an environmental variable set for local_settings
    if os.environ.has_key('CUSTOMSETTINGS') and os.environ['CUSTOMSETTINGS'] == "demo":
        # this sucks, but is a workaround for supporting different settings
        # in the same environment
        from settings_demo import *
    else:
        from localsettings import *
except ImportError:
    pass

####### South Settings #######
#SKIP_SOUTH_TESTS=True
#SOUTH_TESTS_MIGRATE=False

####### Couch Forms & Couch DB Kit Settings #######
from settingshelper import get_dynamic_db_settings
_dynamic_db_settings = get_dynamic_db_settings(COUCH_SERVER_ROOT, COUCH_USERNAME, COUCH_PASSWORD, COUCH_DATABASE_NAME, INSTALLED_APPS)

# create local server and database configs
COUCH_SERVER = _dynamic_db_settings["COUCH_SERVER"]
COUCH_DATABASE = _dynamic_db_settings["COUCH_DATABASE"]

# other urls that depend on the server 
XFORMS_POST_URL = _dynamic_db_settings["XFORMS_POST_URL"]

COUCHDB_DATABASES = [(app_label, COUCH_DATABASE) for app_label in [
        'api',
        'app_manager',
        'auditcare',
        'builds',
        'case',
        'cleanup',
        'couch', # This is necessary for abstract classes in dimagi.utils.couch.undo; otherwise breaks tests
        'couchforms',
        'couchexport',
        'couchlog',
        'hqadmin',
        'domain',
        'forms',
        'groups',
        'hqcase',
        'hqmedia',
        'migration',
        'phone',
        'receiverwrapper',
        'reminders',
        'prescriptions',
        'reports',
        'sms',
        'translations',
        'users',
        'formplayer',
        'xep_hq_server',
        'phonelog',
        'pathfinder',
        'registration'
    ]
]




INSTALLED_APPS += LOCAL_APPS

MIDDLEWARE_CLASSES += LOCAL_MIDDLEWARE_CLASSES

try:
    LOG_FORMAT
except Exception:
    LOG_FORMAT = "%(asctime)s %(levelname)-8s - %(name)-26s %(message)s"

logging.basicConfig(filename=DJANGO_LOG_FILE, format=LOG_FORMAT)

# these are the official django settings
# which really we should be using over the
# above
EMAIL_HOST = EMAIL_SMTP_HOST
EMAIL_PORT = EMAIL_SMTP_PORT
EMAIL_HOST_USER = EMAIL_LOGIN
EMAIL_HOST_PASSWORD = EMAIL_PASSWORD
EMAIL_USE_TLS = True

STANDARD_REPORT_MAP = {
    "Monitor Workers" : ['corehq.apps.reports.standard.CaseActivityReport',
                           'corehq.apps.reports.standard.SubmissionsByFormReport',
                           'corehq.apps.reports.standard.DailySubmissionsReport',
                           'corehq.apps.reports.standard.DailyFormCompletionsReport',
                           'corehq.apps.reports.standard.FormCompletionTrendsReport',
                           'corehq.apps.reports.standard.SubmissionTimesReport',
                           'corehq.apps.reports.standard.SubmitDistributionReport',
                           ],
    "Inspect Data" : ['corehq.apps.reports.standard.SubmitHistory',
                      'corehq.apps.reports.standard.CaseListReport',
                           ]
}
