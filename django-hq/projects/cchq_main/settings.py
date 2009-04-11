# -*- coding: utf-8 -*-
# Django settings for cchq_groups project.

DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)
import os
COMMCARE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__),"../../"))
COMMCARE_THEME = 'default' 

MANAGERS = ADMINS

DATABASE_ENGINE = 'sqlite3'           # 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
DATABASE_NAME = os.path.join(os.path.dirname(__file__),'cchq.db')           # Or path to database file if using sqlite3.
#DATABASE_NAME = 'commcarehq'    # Or path to database file if using sqlite3.
#DATABASE_USER = 'root'             # Not used with sqlite3.
#DATABASE_PASSWORD = 'password'         # Not used with sqlite3.
DATABASE_HOST = ''             # Set to empty string for localhost. Not used with sqlite3.
DATABASE_PORT = ''             # Set to empty string for default. Not used with sqlite3.


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
LOGIN_REDIRECT_URL = '/'
# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True


# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = os.path.join(os.path.dirname(__file__),'media')

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
if DEBUG == True:
    MEDIA_URL = 'http://127.0.0.1:8000/media/'
else:
    MEDIA_URL = 'http://test.commcarehq.org/media/'

#for local testing with localmediaserver.py
#import socket
#MEDIA_HOSTADDR = socket.gethostbyname(socket.gethostname())
#MEDIA_HOST= MEDIA_HOSTADDR + ":" + str(8090)
#MEDIA_URL = 'http://' + MEDIA_HOST + '/media/'

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/media/admin-media/'

# Make this unique, and don't share it with anybody.
SECRET_KEY = '^thynux2u52g@p#q*4!57dfu%^&i^c43watl-9$fh@oa5xy1z4'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.load_template_source',
    'django.template.loaders.app_directories.load_template_source',
    #'django.template.loaders.eggs.load_template_source',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.doc.XViewMiddleware',
)

ROOT_URLCONF = 'cchq_main.urls'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    os.path.join(os.path.dirname(__file__),'templates'),
    
#    os.path.join('../../apps','modelrelationship','templates'),
    os.path.join('../../apps','xformmanager','templates'),
    os.path.join('../../apps','receiver','templates'),
    os.path.join('../../apps','monitorregistry','templates'),
    os.path.join('../../apps','organization','templates'),
    os.path.join('../../apps','djflot','templates'),
)
TEMPLATE_CONTEXT_PROCESSORS = ( 
    "django.core.context_processors.auth",
    "django.core.context_processors.debug",    
    "django.core.context_processors.i18n",
    "django.core.context_processors.media",
    "django.core.context_processors.request",
    
    )


# Patch the python path quick, since we want
# to keep our apps in a different directory

import sys
current_path = os.path.dirname(__file__)
sys.path.append(os.path.join(current_path,"../../apps"))
sys.path.append(os.path.join(current_path,"../../libs"))
sys.path.append(os.path.join(current_path,"../../scripts"))



INSTALLED_APPS = (
    'django.contrib.auth',    
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.admin',    
    'django.contrib.admindocs',
    'django_extensions',
    
    'receiver',
    'modelrelationship',
    'xformmanager',
    'monitorregistry',
    'organization',     
    'djflot',   
)


ugettext = lambda s: s
LANGUAGES = (
  ('en', u'English'),
  ('de', u'Deutsch'),
#  ('es', u'Español'),
#  ('fr', u'Français'),
#  ('sv', u'Svenska'),
#  ('pt-br', u'Português brasileiro'),
#  ('he', u'עברית'),
#  ('ar', u'العربية'),
#  ('it', u'Italiano'),
)

SCRIPT_PATH = (os.path.join(current_path,"../../scripts"))
CSV_PATH = os.path.join(MEDIA_ROOT,'csv')
XFORM_SUBMISSION_PATH = os.path.join(os.path.dirname(__file__),'xform-data')
XSD_REPOSITORY_PATH = os.path.join(os.path.dirname(__file__),'schemas')
ATTACHMENTS_PATH = os.path.join(MEDIA_ROOT,'attachment')
if not os.path.exists(ATTACHMENTS_PATH):
    os.mkdir(ATTACHMENTS_PATH)

if not os.path.exists(SCRIPT_PATH):
    os.mkdir(SCRIPT_PATH)
                     
if not os.path.exists(XFORM_SUBMISSION_PATH):
    os.mkdir(XFORM_SUBMISSION_PATH)
                     
if not os.path.exists(XSD_REPOSITORY_PATH):
    os.mkdir(XSD_REPOSITORY_PATH) 

if not os.path.exists(CSV_PATH):
    os.mkdir(CSV_PATH)

import logging
logging.basicConfig(
    level = 0,
    format = '%(asctime)s %(levelname)s %(message)s',
    filename = os.path.join(os.path.dirname(__file__),'cchq.log'),
    filemode = 'w+'
)

#COMMCARE VARS EXAMPLE, will be appended at the end.
#CCHQ_BUILD_NUMBER=-1
#CCHQ_REVISION_NUMBER=-1
#CCHQ_BUILD_DATE=''


