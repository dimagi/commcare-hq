#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

import os, time
import logging

DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = ()
MANAGERS = ADMINS


# default to the system's timezone settings. this can still be
# overridden in rapidsms.ini [django], by providing one of:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
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

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = '/static'

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
#     'django.template.loaders.eggs.load_template_source',
)

MIDDLEWARE_CLASSES = [
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'corehq.apps.domain.middleware.DomainMiddleware',
    'corehq.apps.users.middleware.UsersMiddleware',
]

ROOT_URLCONF = "urls"

TEMPLATE_CONTEXT_PROCESSORS = [
    "django.core.context_processors.auth",
    "django.core.context_processors.debug",
    "django.core.context_processors.i18n",
    "django.core.context_processors.media",
    "django.core.context_processors.request",
    "corehq.util.context_processors.base_template" # sticks the base template inside all responses
]

TEMPLATE_DIRS = [
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
]


# ====================
# INJECT RAPIDSMS APPS
# ====================
DEFAULT_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'south',
)

HQ_APPS = (
    #'django_extensions',
    'django_digest',
    'django_rest_interface',
    'django_granular_permissions',
    'django_tables',
    'django_user_registration',
    'djangocouch',
    'djangocouchuser',
    'corehq.apps.case',
    'corehq.apps.domain',
    'corehq.apps.hqwebapp',
    'corehq.apps.program',
    'corehq.apps.phone',
    'corehq.apps.logtracker',

    'corehq.apps.releasemanager',
    'corehq.apps.requestlogger',
    'corehq.apps.docs',
    'ota_restore',
    'couchforms',
    'couchexport',
    'corehq.apps.receiver',
    'corehq.apps.app_manager',
    'corehq.apps.new_data',
    'corehq.apps.users',
    'corehq.apps.groups',
    'corehq.apps.reports',
    'xep_hq_server',
)

RAPIDSMS_APPS = (
    # RapidSMS Core
    'djtables',
    'rapidsms',

    # Common Dependencies
    #"rapidsms.contrib.handlers",
    #"rapidsms.contrib.ajax",

    # RapidSMS Apps
    #'rapidsms.contrib.messagelog',
    #'rapidsms.contrib.messaging',
    
    # For Testing
    'rapidsms.contrib.httptester',

    # TODO: customize these and then add them
    # 'default',
)

TABS = [
#    ("message_log", "Message Log"),
#    #("rapidsms.contrib.messagelog.views.message_log", "Message Log"),
#    ("rapidsms.contrib.messaging.views.messaging", "Messaging"),
#    ("rapidsms.contrib.httptester.views.generate_identity", "Message Tester"),
#    ('corehq.apps.hqwebapp.views.dashboard', 'Dashboard'),
#    ('corehq.apps.releasemanager.views.projects', 'Release Manager'),
#    #('corehq.apps.receiver.views.show_submits', 'Submissions'),
#    ('corehq.apps.xforms.views.dashboard', 'XForms'),
    ("corehq.apps.reports.views.default", "Reports"),
    ("corehq.apps.app_manager.views.default", "Applications"),
#    ("corehq.apps.hqwebapp.views.messages", "Messages"),
    ("corehq.apps.users.views.users", "Users and Settings"),
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

####### Release Manager App settings  #######
RELEASE_FILE_PATH=os.path.join("data","builds")

####### Photo App settings  #######
PHOTO_IMAGE_PATH=os.path.join("data","photos")


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

# these are the official django settings
# which really we should be using over the
# above
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_HOST_USER = "user@domain.com"
EMAIL_HOST_PASSWORD = "changeme"
EMAIL_USE_TLS = True

PAGINATOR_OBJECTS_PER_PAGE = 15
PAGINATOR_MAX_PAGE_LINKS = 5


# xep_hq_server settings
XEP_AUTHORIZE = 'corehq.apps.app_manager.models.authorize_xform_edit'
XEP_GET_XFORM = 'corehq.apps.app_manager.models.get_xform'
XEP_PUT_XFORM = 'corehq.apps.app_manager.models.put_xform'
GET_URL_BASE  = 'corehq.util.webutils.get_url_base'


DJANGO_LOG_FILE = "/var/log/commcarehq.django.log"
LOG_SIZE = 1000000
LOG_LEVEL   = "DEBUG"
LOG_FILE    = "/var/log/commcarehq.router.log"
LOG_FORMAT  = "[%(name)s]: %(message)s"
LOG_BACKUPS = 256 # number of logs to keep


# import local settings if we find them
try:
    #try to see if there's an environmental variable set for local_settings
    import sys, os
    if os.environ.has_key('LOCALSETTINGS'):
        localpath = os.path.dirname(os.environ['LOCALSETTINGS'])
        sys.path.insert(0, localpath)
    from localsettings import *
except ImportError:
    pass

try:
    INSTALLED_APPS = DEFAULT_APPS + HQ_APPS + RAPIDSMS_APPS + LOCAL_APPS
except:
    INSTALLED_APPS = DEFAULT_APPS + HQ_APPS + RAPIDSMS_APPS


# create data directories required by commcarehq
import os
root = os.path.dirname(__file__)
if not os.path.isdir(os.path.join(root,'data')):
    os.mkdir(os.path.join(root,'data'))
if not os.path.isdir(os.path.join(root,'data','submissions')):
    os.mkdir(os.path.join(root,'data','submissions'))
if not os.path.isdir(os.path.join(root,'data','attachments')):
    os.mkdir(os.path.join(root,'data','attachments'))
if not os.path.isdir(os.path.join(root,'data','schemas')):
    os.mkdir(os.path.join(root,'data','schemas'))


XFORMS_FORM_TRANSLATE_JAR="submodules/core-hq-src/lib/form_translate.jar"

####### South Settings #######
#SKIP_SOUTH_TESTS=True
#SOUTH_TESTS_MIGRATE=False

####### RapidSMS Settings #######
INSTALLED_BACKENDS = {
    #"att": {
    #    "ENGINE": "rapidsms.backends.gsm",
    #    "PORT": "/dev/ttyUSB0"
    #},
    #"verizon": {
    #    "ENGINE": "rapidsms.backends.gsm,
    #    "PORT": "/dev/ttyUSB1"
    #},
    "message_tester": {
        "ENGINE": "rapidsms.backends.bucket"
    }
}

from settingshelper import get_dynamic_db_settings
####### Couch Forms & Couch DB Kit Settings #######
_dynamic_db_settings = get_dynamic_db_settings(COUCH_SERVER_ROOT, COUCH_USERNAME, COUCH_PASSWORD, COUCH_DATABASE_NAME, INSTALLED_APPS)

# create local server and database configs
COUCH_SERVER = _dynamic_db_settings["COUCH_SERVER"]
COUCH_DATABASE = _dynamic_db_settings["COUCH_DATABASE"]

# other urls that depend on the server 
XFORMS_POST_URL = _dynamic_db_settings["XFORMS_POST_URL"]

COUCHDB_DATABASES = [(app_label, COUCH_DATABASE) for app_label in [
        'couchforms',
        'couchexport',
        'app_manager',
        'new_data',
        'case',
        'users',
        'groups',
        'domain',
        'reports',
        'xep_hq_server'
    ]
]


SKIP_SOUTH_TESTS = True

TEST_RUNNER = 'testrunner.HqTestSuiteRunner'
try:
    INSTALLED_APPS += LOCAL_APPS
except:
    pass

AUTH_PROFILE_MODULE = 'users.HqUserProfile'

XFORMPLAYER_URL = 'http://xforms.dimagi.com/play_remote/'

logging.basicConfig(filename=DJANGO_LOG_FILE)