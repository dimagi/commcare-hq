import os
import sys

####### Database config. This assumes Postgres ####### 

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'commcarehq',
        'USER': 'postgres',
        'PASSWORD': '******'
    }
}

####### Couch Config ######
COUCH_SERVER_ROOT = '127.0.0.1:5984'
COUCH_USERNAME = 'admin'
COUCH_PASSWORD = '********'
COUCH_DATABASE_NAME = 'commcarehq'

####### # Email setup ########
# email settings: these ones are the custom hq ones
EMAIL_LOGIN = "notifications@dimagi.com"
EMAIL_PASSWORD="******"
EMAIL_SMTP_HOST="smtp.gmail.com"
EMAIL_SMTP_PORT=587

ADMINS = (('HQ Dev Team', 'commcarehq-dev+www-notifications@dimagi.com'),)
BUG_REPORT_RECIPIENTS = ['commcarehq-support@dimagi.com']
NEW_DOMAIN_RECIPIENTS = ['commcarehq-dev+newdomain@dimagi.com']

####### Log/debug setup ########

DEBUG = False
TEMPLATE_DEBUG = DEBUG

# The django logs will end up here
DJANGO_LOG_FILE = os.path.join('/opt/www.commcarehq.org_project/log',"www.commcarehq.org.django.log")

SEND_BROKEN_LINK_EMAILS = True
CELERY_SEND_TASK_ERROR_EMAILS = True

####### Static files ########

filepath = os.path.abspath(os.path.dirname(__file__))
# media for user uploaded media.  in general this won't be used at all.
MEDIA_ROOT = os.path.join(filepath,'mediafiles') 
STATIC_ROOT = os.path.join(filepath,'staticfiles')


####### Bitly ########

BITLY_LOGIN = 'dimagi'
BITLY_APIKEY = '*******'

####### Jar signing config ########

_ROOT_DIR  = os.path.dirname(os.path.abspath(__file__))
JAR_SIGN = dict(
    jad_tool = os.path.join(_ROOT_DIR, "submodules", "core-hq-src", "corehq", "apps", "app_manager", "JadTool.jar"),
    key_store = os.path.join(os.path.dirname(os.path.dirname(_ROOT_DIR)), "DimagiKeyStore"),
    key_alias = "javarosakey",
    store_pass = "*******",
    key_pass = "*******",
)

####### XEP stuff - TODO: remove this section when we retire XEP ########

REFLEXIVE_URL_BASE = "https://localhost:8001"
def get_url_base():
    return REFLEXIVE_URL_BASE
GET_URL_BASE  = 'settings.get_url_base'


####### SMS Config ########

# Mach

SMS_GATEWAY_URL = "http://gw1.promessaging.com/sms.php"
SMS_GATEWAY_PARAMS = "id=******&pw=******&dnr=%(phone_number)s&msg=%(message)s&snr=DIMAGI"

# Unicel
UNICEL_CONFIG = {"username": "Dimagi",
                 "password": "******",
                 "sender": "Promo" }

####### Custom reports ########

CUSTOM_REPORT_MAP = {
    "domain_name": [
        'path.to.CustomReport',
    ]
}

####### Domain sync / de-id ########

DOMAIN_SYNCS = { 
    "domain_name": { 
        "target": "target_db_name",
        "transform": "corehq.apps.domainsync.transforms.deidentify_domain" 
    }
}
DOMAIN_SYNC_APP_NAME_MAP = { "app_name": "new_app_name" }

####### Touchforms config #######

XFORMS_PLAYER_URL = 'http://127.0.0.1:4444'

TOUCHFORMS_API_USER = 'admin@example.com'
TOUCHFORMS_API_PASSWORD = 'password'

####### Selenium tests config ########

TEST_ADMIN_USERNAME = 'admin@example.com'
TEST_ADMIN_PASSWORD = 'password'
TEST_BASE_URL = 'http://localhost:8000'
TEST_ADMIN_PROJECT = 'project'

TEST_MOBILE_WORKER_USERNAME = 'user@project.commcarehq.org'
TEST_MOBILE_WORKER_PASSWORD = 'password'
SELENIUM_DRIVER = 'Chrome'
SELENIUM_XVFB = False
SELENIUM_XVFB_DISPLAY_SIZE = (1024, 768)

####### Misc / HQ-specific Config ########

DEFAULT_PROTOCOL = "https" # or http
OVERRIDE_LOCATION="https://www.commcarehq.org"


GOOGLE_ANALYTICS_ID = '*******'

AXES_LOCK_OUT_AT_FAILURE = False
LUCENE_ENABLED = True

INSECURE_URL_BASE = "http://submit.commcarehq.org"

PREVIEWER_RE = r'^.*@dimagi\.com$'
GMAPS_API_KEY = '******'
FORMTRANSLATE_TIMEOUT = 5
#LOCAL_APPS = ('django_cpserver','dimagi.utils')

# list of domains to enable ADM reporting on
ADM_ENABLED_PROJECTS = []
