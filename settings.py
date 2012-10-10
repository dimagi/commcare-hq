#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

import os
import logging
from django.contrib import messages


CACHE_BACKEND = 'memcached://127.0.0.1:11211/'

DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = ()
MANAGERS = ADMINS


# default to the system's timezone settings
TIME_ZONE = "UTC"


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
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder"
)

STATICFILES_DIRS = (
    ('formdesigner', os.path.join(filepath,'submodules', 'formdesigner')),
)

DJANGO_LOG_FILE = "%s/%s" % (filepath, "commcarehq.django.log")

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
    'casexml.apps.phone.middleware.SyncTokenMiddleware',
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
    'django.core.context_processors.static',
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
    'django.contrib.staticfiles', 
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
    'corehq.apps.cloudcare',
    'corehq.apps.appstore',
    'corehq.apps.domain',
    'corehq.apps.domainsync',
    'corehq.apps.hqadmin',
    'corehq.apps.hqcase',
    'corehq.apps.hqcouchlog',
    'corehq.apps.hqwebapp',
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
    'corehq.apps.orgs',
    'corehq.apps.fixtures',
    'corehq.apps.importer',
    'corehq.apps.reminders',
    'corehq.apps.prescriptions',
    'corehq.apps.translations',
    'corehq.apps.users',
    'corehq.apps.settings',
    'corehq.apps.ota',
    'corehq.apps.groups',
    'corehq.apps.sms',
    'corehq.apps.smsforms',
    'corehq.apps.ivr',
    'corehq.apps.tropo',
    'corehq.apps.yo',
    'corehq.apps.registration',
    'corehq.apps.unicel',
    'corehq.apps.reports',
    'corehq.apps.data_interfaces',
    'corehq.apps.adm',
    'corehq.apps.hq_bootstrap',
    'corehq.apps.builds',
    'corehq.apps.orgs',
    'corehq.apps.api',
    'corehq.apps.indicators',
    'corehq.couchapps',
    'corehq.apps.selenium',
    'sofabed.forms',
    'soil',
    'corehq.apps.hqsofabed',
    'touchforms.formplayer',
    'hqbilling',
    'phonelog',
    'hutch',
    'loadtest',
    
    # custom reports
    'a5288',
    'bihar',
    'dca',
    'hsph',
    'mvp',
    'pathfinder',
    'pathindia',
)

REFLEXIVE_URL_BASE = "localhost:8000"

INSTALLED_APPS = DEFAULT_APPS + HQ_APPS

TABS = [
    ("corehq.apps.appstore.views.project_info", "Info", lambda request: request.project.is_snapshot),
    ("corehq.apps.reports.views.default", "Reports", lambda request: not request.project.is_snapshot),
    ("corehq.apps.data_interfaces.views.default", "Manage Data", lambda request: request.couch_user.can_edit_data()),
    ("corehq.apps.app_manager.views.default", "Applications"),
    ("corehq.apps.cloudcare.views.default", "CloudCare", lambda request: request.couch_user.can_edit_data()),
    ("corehq.apps.sms.views.messaging", "Messages", lambda request: not request.project.is_snapshot),
    ("corehq.apps.settings.views.default", "Settings & Users", lambda request: request.couch_user.can_edit_commcare_users() or request.couch_user.can_edit_web_users()),
    ("corehq.apps.hqadmin.views.default", "Admin Reports", "is_superuser"),
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
FIXTURE_GENERATORS = [
    "corehq.apps.users.fixturegenerators.user_groups",
    "corehq.apps.fixtures.fixturegenerators.item_lists",
]

GET_URL_BASE  = 'dimagi.utils.web.get_url_base'

SMS_GATEWAY_URL = "http://localhost:8001/"
SMS_GATEWAY_PARAMS = "user=my_username&password=my_password&id=%(phone_number)s&text=%(message)s"

# celery
BROKER_URL = 'django://' #default django db based


SKIP_SOUTH_TESTS = True
#AUTH_PROFILE_MODULE = 'users.HqUserProfile'
TEST_RUNNER = 'testrunner.HqTestSuiteRunner'
HQ_ACCOUNT_ROOT = "commcarehq.org" # this is what gets appended to @domain after your accounts

XFORMS_PLAYER_URL = "http://localhost:4444/"  # touchform's setting

####### Couchlog config ######

SUPPORT_EMAIL = "commcarehq-support@dimagi.com"
COUCHLOG_BLUEPRINT_HOME = "%s%s" % (STATIC_URL, "hqwebapp/stylesheets/blueprint/")
COUCHLOG_DATATABLES_LOC = "%s%s" % (STATIC_URL, "hqwebapp/datatables-1.9/js/jquery.dataTables.min.js")

# These allow HQ to override what shows up in couchlog (add a domain column)
COUCHLOG_TABLE_CONFIG = {"id_column":       0,
                         "archived_column": 1,
                         "date_column":     2,
                         "message_column":  4,
                         "actions_column":  8,
                         "email_column":    9,
                         "no_cols":         10}
COUCHLOG_DISPLAY_COLS = ["id", "archived?", "date", "exception type",
                         "message", "domain", "user", "url", "actions", "report"]
COUCHLOG_RECORD_WRAPPER = "corehq.apps.hqcouchlog.wrapper"
COUCHLOG_DATABASE_NAME = "commcarehq-couchlog"

# couchlog/case search
LUCENE_ENABLED = False

# sofabed
FORMDATA_MODEL = 'hqsofabed.HQFormData'



# unicel sms config
UNICEL_CONFIG = {"username": "Dimagi",
                 "password": "changeme",
                 "sender": "Promo" }

# mach sms config
MACH_CONFIG = {"username": "Dimagi",
               "password": "changeme",
               "service_profile": "changeme"
               }

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
GOOGLE_ANALYTICS_ID = ''

# for touchforms maps
GMAPS_API_KEY = "changeme"

# for touchforms authentication
TOUCHFORMS_API_USER = "changeme"
TOUCHFORMS_API_PASSWORD = "changeme"

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
from settingshelper import get_dynamic_db_settings, make_couchdb_tuple
_dynamic_db_settings = get_dynamic_db_settings(COUCH_SERVER_ROOT, COUCH_USERNAME, COUCH_PASSWORD, COUCH_DATABASE_NAME, INSTALLED_APPS)

# create local server and database configs
COUCH_SERVER = _dynamic_db_settings["COUCH_SERVER"]
COUCH_DATABASE = _dynamic_db_settings["COUCH_DATABASE"]

# other urls that depend on the server
XFORMS_POST_URL = _dynamic_db_settings["XFORMS_POST_URL"]


COUCHDB_APPS = [
        'adm',
        'api',
        'app_manager',
        'appstore',
        'orgs',
        'auditcare',
        'builds',
        'case',
        'cleanup',
        'cloudcare',
        'couch', # This is necessary for abstract classes in dimagi.utils.couch.undo; otherwise breaks tests
        'couchforms',
        'couchexport',
        'hqadmin',
        'domain',
        'forms',
        'fixtures',
        'groups',
        'hqcase',
        'hqmedia',
        'importer',
        'indicators',
        'migration',
        'phone',
        'receiverwrapper',
        'reminders',
        'prescriptions',
        'reports',
        'sms',
        'smsforms',
        'translations',
        'users',
        'formplayer',
        'phonelog',
        'registration',
        'hutch',
        'hqbilling',
        'couchlog',
        
        # custom reports
        'bihar'
        'dca',
        'hsph',
        'mvp',
        'pathfinder',
        'pathindia',
]


COUCHDB_DATABASES = [make_couchdb_tuple(app_label, COUCH_DATABASE) for app_label in COUCHDB_APPS ]

INSTALLED_APPS += LOCAL_APPS

MIDDLEWARE_CLASSES += LOCAL_MIDDLEWARE_CLASSES

LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
        },
        'simple': {
            'format': '%(levelname)s %(message)s'
        },
    },
    'handlers': {
        'console':{
            'level':'INFO',
            'class':'logging.StreamHandler',
            'formatter': 'simple'
        },
        'file' : {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'formatter': 'verbose',
            'filename': DJANGO_LOG_FILE
        },
        'couchlog':{
            'level':'WARNING',
            'class':'couchlog.handlers.CouchHandler',
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
        }
    },
    'loggers': {
        '': {
            'handlers':['console', 'file', 'couchlog'],
            'propagate': True,
            'level':'INFO',
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
        }
    }
}

# these are the official django settings
# which really we should be using over the custom ones
EMAIL_HOST = EMAIL_SMTP_HOST
EMAIL_PORT = EMAIL_SMTP_PORT
EMAIL_HOST_USER = EMAIL_LOGIN
EMAIL_HOST_PASSWORD = EMAIL_PASSWORD
EMAIL_USE_TLS = True

DATA_INTERFACE_MAP = {
    'Case Management' : [
        'corehq.apps.data_interfaces.interfaces.CaseReassignmentInterface',
        'corehq.apps.importer.base.ImportCases',
    ]
}
APPSTORE_INTERFACE_MAP = {
    'App Store' : [
        'corehq.apps.appstore.interfaces.CommCareExchangeAdvanced'
    ]
}

PROJECT_REPORT_MAP = {
    "Monitor Workers" : [
        'corehq.apps.reports.standard.monitoring.CaseActivityReport',
        'corehq.apps.reports.standard.monitoring.SubmissionsByFormReport',
        'corehq.apps.reports.standard.monitoring.DailySubmissionsReport',
        'corehq.apps.reports.standard.monitoring.DailyFormCompletionsReport',
        'corehq.apps.reports.standard.monitoring.FormCompletionTrendsReport',
        'corehq.apps.reports.standard.monitoring.FormCompletionVsSubmissionTrendsReport',
        'corehq.apps.reports.standard.monitoring.SubmissionTimesReport',
        'corehq.apps.reports.standard.monitoring.SubmitDistributionReport',
    ],
    "Inspect Data" : [
        'corehq.apps.reports.standard.inspect.SubmitHistory',
        'corehq.apps.reports.standard.inspect.CaseListReport',
        'corehq.apps.reports.standard.inspect.MapReport',
    ],
    "Raw Data" : [
        'corehq.apps.reports.standard.export.ExcelExportReport',
        'corehq.apps.reports.standard.export.CaseExportReport',
        'corehq.apps.reports.standard.export.DeidExportReport',
    ],
    "Manage Deployments" : [
        'corehq.apps.reports.standard.deployments.ApplicationStatusReport',
        'corehq.apps.receiverwrapper.reports.SubmissionErrorReport',
        'phonelog.reports.FormErrorReport',
        'phonelog.reports.DeviceLogDetailsReport'
    ]
}

CUSTOM_REPORT_MAP = {
    ## legacy custom reports. do not follow practices followed here
    "pathfinder": {
        'Custom Reports': [
                   'pathfinder.models.PathfinderHBCReport',
                   'pathfinder.models.PathfinderProviderReport',
                   'pathfinder.models.PathfinderWardSummaryReport'
                    ]
                },
    "dca-malawi": {
        'Custom Reports': [
                   'dca.reports.ProjectOfficerReport',
                   'dca.reports.PortfolioComparisonReport',
                   'dca.reports.PerformanceReport',
                   'dca.reports.PerformanceRatiosReport'
                   ]
                },
    "eagles-fahu": {
        'Custom Reports': [
                   'dca.reports.ProjectOfficerReport',
                   'dca.reports.PortfolioComparisonReport',
                   'dca.reports.PerformanceReport',
                   'dca.reports.PerformanceRatiosReport'],
                },
    ## end legacy custom reports
    "hsph": {
        'Field Management Reports': [
                    'hsph.reports.field_management.DCOActivityReport',
                    'hsph.reports.field_management.FieldDataCollectionActivityReport',
                    'hsph.reports.field_management.HVFollowUpStatusReport',
                    'hsph.reports.field_management.HVFollowUpStatusSummaryReport',
                    'hsph.reports.field_management.DCOProcessDataReport'
                    ],
        'Project Management Reports': [
                    'hsph.reports.project_management.ProjectStatusDashboardReport',
                    'hsph.reports.project_management.ImplementationStatusDashboardReport'
                    ],
        'Call Center Reports': [
                    'hsph.reports.call_center.DCCActivityReport',
                    'hsph.reports.call_center.CallCenterFollowUpSummaryReport'
                    ],
        'Data Summary Reports': [
                    'hsph.reports.data_summary.PrimaryOutcomeReport',
                    'hsph.reports.data_summary.SecondaryOutcomeReport']
    },
    "pathindia": {
        'Custom Reports': [
                    'pathindia.reports.PathIndiaKrantiReport'
        ]
    },
    "mvp-sauri": {
        "Custom Reports": [
                    'mvp.reports.MVISHealthCoordinatorReport'
        ]
    },
    "mvp-potou": {
        "Custom Reports": [
                    'mvp.reports.MVISHealthCoordinatorReport'
        ]
    },
    # todo: giovanni, you should fix this report at some point.
    "a5288": {
        "Custom Reports": ["a5288.reports.MissedCallbackReport"]
    },
    "a5288-test": {
        "Custom Reports": ["a5288.reports.MissedCallbackReport"]
    },
    "care-bihar": {
        "Custom Reports": ["bihar.reports.supervisor.FamilyPlanningReport",
                           "bihar.reports.supervisor.TeamDetailsReport",
                           "bihar.reports.supervisor.TeamNavReport",
                           "bihar.reports.supervisor.MotherListReport",
                           "bihar.reports.supervisor.PregnanciesRegistered",
                           "bihar.reports.supervisor.NoBPCounseling",
                           "bihar.reports.supervisor.RecentDeliveries",]
    }
#    "test": [
#        'corehq.apps.reports.deid.FormDeidExport',
#    ]
}

BILLING_REPORT_MAP = {
    "Manage SMS Backend Rates": [
        "hqbilling.reports.backend_rates.DimagiRateReport",
        "hqbilling.reports.backend_rates.MachRateReport",
        "hqbilling.reports.backend_rates.TropoRateReport",
        "hqbilling.reports.backend_rates.UnicelRateReport"
    ],
    "Billing Details": [
        "hqbilling.reports.details.SMSDetailReport",
        "hqbilling.reports.details.MonthlyBillReport"
    ],
    "Billing Tools": [
        "hqbilling.reports.tools.BillableCurrencyReport",
        "hqbilling.reports.tools.TaxRateReport"
    ]
}

ADM_SECTION_MAP = {
    "Supervisor Report": [
        'corehq.apps.adm.reports.supervisor.SupervisorReportsADMSection',
    ],
}

ADM_ADMIN_INTERFACE_MAP = {
    "ADM Default Columns": [
        'corehq.apps.adm.admin.columns.ReducedADMColumnInterface',
        'corehq.apps.adm.admin.columns.DaysSinceADMColumnInterface',
        'corehq.apps.adm.admin.columns.ConfigurableADMColumnInterface'
    ],
    "ADM Default Reports": [
        'corehq.apps.adm.admin.reports.ADMReportAdminInterface',
    ]
}

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
