# Django settings for datahq project.
import os

DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)

MANAGERS = ADMINS

#Database settings should be stored in your settings_local file


# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'America/New_York'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

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
ADMIN_MEDIA_PREFIX = '/static/hqwebapp/admin-media/'

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'fixme'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.load_template_source',
    'django.template.loaders.app_directories.load_template_source',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'corehq.apps.domain.middleware.DomainMiddleware',
    'django_digest.middleware.HttpDigestMiddleware',
)


ROOT_URLCONF = 'urls'


TEMPLATE_CONTEXT_PROCESSORS = (
    "django.core.context_processors.auth",
    "django.core.context_processors.debug",
    "django.core.context_processors.i18n",
    "django.core.context_processors.media",
    "django.core.context_processors.request",
    "corehq.util.context_processors.base_template", # sticks the base template inside all responses    
)


DEFAULT_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'south',
    
    #'gunicorn',
    #'devserver',    
    
)

HQ_APPS = (    
    'django_digest',
    'django_user_registration',
    'corehq.apps.domain',
    'corehq.apps.receiver',
    'corehq.apps.hqwebapp',
    'corehq.apps.program',
    'corehq.apps.xforms',
    'casexml.apps.phone',
    'releasemanager',
    'requestlogger',
)

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

INSTALLED_APPS = DEFAULT_APPS + HQ_APPS

# after login, django redirects to this URL
# rather than the default 'accounts/profile'
LOGIN_REDIRECT_URL='/'

#Relative paths to the settings.py
CUR_DIR = os.path.dirname(__file__)
BASE_DIR = os.path.abspath(os.path.join(CUR_DIR,"..",".."))

####### Receiver Settings #######
RECEIVER_SUBMISSION_PATH=os.path.join(BASE_DIR,"data","submissions")
RECEIVER_ATTACHMENT_PATH=os.path.join(BASE_DIR,"data","attachments")
RECEIVER_EXPORT_PATH=os.path.join(BASE_DIR,"data")

####### XForms Settings #######
XFORMS_SCHEMA_PATH=os.path.join(BASE_DIR,"data","schemas")
XFORMS_EXPORT_PATH=os.path.join(BASE_DIR,"data","exports")
XFORMS_FORM_TRANSLATE_JAR=os.path.join(BASE_DIR,"lib","form_translate.jar")

####### ReleaseManager settings  #######
RELEASE_FILE_PATH="data/release"

# create data directories required by xforms app
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

#####Encryption Keys######
KEYSTORE_PATH=os.path.join(BASE_DIR,"data","keystore")


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


####### Shared/Global/UI Settings ######

# restyle some templates
BASE_TEMPLATE="hqwebapp/base.html"
LOGIN_TEMPLATE="login_and_password/login.html"
LOGGEDOUT_TEMPLATE="loggedout.html"

# email settings: these ones are the custom hq ones
EMAIL_LOGIN="notifications@dimagi.com"
EMAIL_PASSWORD="alpha321"
EMAIL_SMTP_HOST="smtp.gmail.com"
EMAIL_SMTP_PORT=587

# these are the official django settings
# which really we should be using over the
# above
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_HOST_USER = "notifications@dimagi.com"
EMAIL_HOST_PASSWORD = "alpha321"
EMAIL_USE_TLS = True

TABS = [
    ('corehq.apps.hqwebapp.views.dashboard', 'Dashboard'),
    ('corehq.apps.xforms.views.dashboard', 'XForms'),
    ('corehq.apps.receiver.views.show_submits', 'Submissions'),    
]

DIGEST_ENFORCE_NONCE_COUNT = False

# import local settings if we find them
try:
    #try to see if there's an environmental variable set for local_settings
    import sys
    if os.environ.has_key('SETTINGS_LOCAL'):
        localpath = os.path.dirname(os.environ['SETTINGS_LOCAL'])
        sys.path.insert(0, localpath)
    from settings_local import *
except ImportError:
    pass

DJANGO_LOG_FILE = "/var/log/datahq/datahq.django.log"
LOG_SIZE = 1000000
LOG_LEVEL   = "ERROR"
LOG_FILE    = "/var/log/datahq/datahq.log"
LOG_FORMAT  = "[%(name)s]: %(message)s"

