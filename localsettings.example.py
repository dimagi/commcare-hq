import os
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
COUCH_HTTPS = True #recommended production value if enabling https
COUCH_SERVER_ROOT = '127.0.0.1:5984' #6984 for https couch
COUCH_USERNAME = 'admin'
COUCH_PASSWORD = '********'
COUCH_DATABASE_NAME = 'commcarehq'

####### # Email setup ########
# email settings: these ones are the custom hq ones
EMAIL_LOGIN = "notifications@dimagi.com"
EMAIL_PASSWORD = "******"
EMAIL_SMTP_HOST = "smtp.gmail.com"
EMAIL_SMTP_PORT = 587

ADMINS = (('HQ Dev Team', 'commcarehq-dev+www-notifications@dimagi.com'),)
BUG_REPORT_RECIPIENTS = ['commcarehq-support@dimagi.com']
NEW_DOMAIN_RECIPIENTS = ['commcarehq-dev+newdomain@dimagi.com']
EXCHANGE_NOTIFICATION_RECIPIENTS = ['commcarehq-dev+exchange@dimagi.com']

####### Log/debug setup ########

DEBUG = False
TEMPLATE_DEBUG = DEBUG

# log directories must exist and be writeable!
DJANGO_LOG_FILE = "/var/log/commcare-hq/commcare-hq.django.log"
LOG_FILE = "/var/log/commcare-hq/commcare-hq.log"

SEND_BROKEN_LINK_EMAILS = True
CELERY_SEND_TASK_ERROR_EMAILS = True

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

####### Touchforms config - for CloudCare #######

XFORMS_PLAYER_URL = 'http://127.0.0.1:4444'

TOUCHFORMS_API_USER = 'admin@example.com'
TOUCHFORMS_API_PASSWORD = 'password'


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

# prod settings
SOIL_DEFAULT_CACHE = "redis"
SOIL_BACKEND = "soil.CachedDownload"

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.memcached.MemcachedCache',
        'LOCATION': 'localhost:11211',
    },
    'redis': {
        'BACKEND': 'redis_cache.cache.RedisCache',
        'LOCATION': 'localhost:6379',
        'OPTIONS': {},
    }
}

ELASTICSEARCH_HOST = 'localhost' #on both a local and a distributed environment this should be
# localhost
ELASTICSEARCH_PORT = 9200

# our production logstash aggregation
LOGSTASH_DEVICELOG_PORT = 10777
LOGSTASH_COUCHLOG_PORT = 10888
LOGSTASH_AUDITCARE_PORT = 10999
LOGSTASH_HOST = 'localhost'

LOCAL_PILLOWTOPS = []

####### Selenium tests config ########

SELENIUM_SETUP = {
    # apps (or app-qualified testcase classes or methods) to skip testing
    'EXCLUDE_APPS': [],

    # Firefox, Chrome, Ie, or Remote
    'BROWSER': 'Chrome',
    
    # Necessary if using Remote selenium driver
    'REMOTE_URL': None,
    
    # If not using Remote, allows you to open browsers in a hidden virtual X Server
    'USE_XVFB': True,
    'XVFB_DISPLAY_SIZE': (1024, 768),
}

SELENIUM_USERS = {
    # 'WEB_USER' is optional; if not set, some tests that want a web user will
    # try to use ADMIN instead
    'ADMIN': {
        'USERNAME': 'foo@example.com',
        'PASSWORD': 'password',
        'URL': 'http://localhost:8000',
        'PROJECT': 'project_name',
        'IS_SUPERUSER': False
    },

    'WEB_USER': {
        'USERNAME': 'foo@example.com',
        'PASSWORD': 'password',
        'URL': 'http://localhost:8000',
        'PROJECT': 'mike',
        'IS_SUPERUSER': False
    },

    'MOBILE_WORKER': {
        'USERNAME': 'user@project_name.commcarehq.org',
        'PASSWORD': 'password',
        'URL': 'http://localhost:8000'
    }
}

SELENIUM_APP_SETTINGS = {
    'reports': {
        'MAX_PRELOAD_TIME': 20,
        'MAX_LOAD_TIME': 30,
    },
}
