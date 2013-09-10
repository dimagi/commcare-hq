import os
####### Database config. This assumes Postgres ####### 

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'commcarehq',
        'USER': 'postgres',
        'PASSWORD': '******',
        'HOST': 'localhost',
        'PORT': '5432'
    }
}

### Reporting database
SQL_REPORTING_DATABASE_URL = "postgresql://username:****@localhost:5432/commcarehq_reporting"

####### Couch Config ######
COUCH_HTTPS = False # recommended production value is True if enabling https
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

# Print emails to console so there is no danger of spamming, but you can still get registration URLs
EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend'

ADMINS = (('HQ Dev Team', 'commcarehq-dev+www-notifications@dimagi.com'),)
BUG_REPORT_RECIPIENTS = ['commcarehq-support@dimagi.com']
NEW_DOMAIN_RECIPIENTS = ['commcarehq-dev+newdomain@dimagi.com']
EXCHANGE_NOTIFICATION_RECIPIENTS = ['commcarehq-dev+exchange@dimagi.com']

SERVER_EMAIL = 'commcarehq-noreply@dimagi.com' #the physical server emailing - differentiate if needed
DEFAULT_FROM_EMAIL = 'commcarehq-noreply@dimagi.com'
SUPPORT_EMAIL = "commcarehq-support@dimagi.com"
EMAIL_SUBJECT_PREFIX = '[commcarehq] '
SERVER_ENVIRONMENT = 'changeme' #identify the target type of this running environment

####### Log/debug setup ########

DEBUG = True
TEMPLATE_DEBUG = DEBUG

# log directories must exist and be writeable!
DJANGO_LOG_FILE = "/tmp/commcare-hq.django.log"
LOG_FILE = "/tmp/commcare-hq.log"

SEND_BROKEN_LINK_EMAILS = True
CELERY_SEND_TASK_ERROR_EMAILS = True
CELERY_PERIODIC_QUEUE = 'celery' # change this to something else if you want a different queue for periodic tasks
CELERY_FLOWER_URL = 'http://127.0.0.1:5555'

####### Bitly ########

BITLY_LOGIN = 'dimagi'
BITLY_APIKEY = '*******'


####### Jar signing config ########

_ROOT_DIR  = os.path.dirname(os.path.abspath(__file__))
JAR_SIGN = dict(
    jad_tool = os.path.join(_ROOT_DIR, "corehq", "apps", "app_manager", "JadTool.jar"),
    key_store = os.path.join(os.path.dirname(os.path.dirname(_ROOT_DIR)), "DimagiKeyStore"),
    key_alias = "javarosakey",
    store_pass = "*******",
    key_pass = "*******",
)

####### SMS Config ########

# Mach

SMS_GATEWAY_URL = "http://gw1.promessaging.com/sms.php"
SMS_GATEWAY_PARAMS = "id=******&pw=******&dnr=%(phone_number)s&msg=%(message)s&snr=DIMAGI"

# Unicel
UNICEL_CONFIG = {"username": "Dimagi",
                 "password": "******",
                 "sender": "Promo" }

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

# email and password for an admin django user, such as one created with
# ./manage.py bootstrap <project-name> <email> <password>
TOUCHFORMS_API_USER = 'admin@example.com'
TOUCHFORMS_API_PASSWORD = 'password'


####### Misc / HQ-specific Config ########

DEFAULT_PROTOCOL = "http" # or https
OVERRIDE_LOCATION="https://www.commcarehq.org"

#Set your analytics IDs here for GA and pingdom RUM
ANALYTICS_IDS = {
    'GOOGLE_ANALYTICS_ID': '*******',
    'PINGDOM_ID': '*****'
}

AXES_LOCK_OUT_AT_FAILURE = False
LUCENE_ENABLED = True

INSECURE_URL_BASE = "http://submit.commcarehq.org"

PREVIEWER_RE = r'^.*@dimagi\.com$'
GMAPS_API_KEY = '******'
FORMTRANSLATE_TIMEOUT = 5
LOCAL_APPS = (
#    'django_coverage', # Adds `python manage.py test_coverage` (settings below)
#    'debug_toolbar',   # Adds a retractable panel to every page giving profiling & debugging info
#    'couchdebugpanel', # Adds couch info to said toolbar
#    'devserver',       # Adds improved dev server that also prints SQL on the console (for AJAX, etc, when you cannot use debug_toolbar)
#    'django_cpserver', # Another choice for a replacement server
#    'dimagi.utils'     
)

# list of domains to enable ADM reporting on
ADM_ENABLED_PROJECTS = []

# prod settings
SOIL_DEFAULT_CACHE = "redis"
SOIL_BACKEND = "soil.CachedDownload"

# reports cache
REPORT_CACHE = 'default' # or e.g. 'redis'

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.memcached.MemcachedCache',
        'LOCATION': 'localhost:11211',
    },
    'redis': {
        'BACKEND': 'redis_cache.cache.RedisCache',
        'LOCATION': 'localhost:6379:0',
        'OPTIONS': {},
    },
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

#If there are existing doc_ids and case_ids you want to check directly - they are referenced
#in your localsettings for more accurate direct checks, otherwise use view based which can be inaccurate.
ES_CASE_CHECK_DIRECT_DOC_ID = None
ES_XFORM_CHECK_DIRECT_DOC_ID = None

####### API throttling #####

API_THROTTLE_REQUESTS=20  # number of requests allowed per timeframe
API_THROTTLE_TIMEFRAME=10 # seconds

####### django-coverage config ########

COVERAGE_REPORT_HTML_OUTPUT_DIR='coverage-html'
COVERAGE_MODULE_EXCLUDES= ['tests$', 'settings$', 'urls$', 'locale$',
                           'common.views.test', '^django', 'management', 'migrations',
                           '^south', '^djcelery', '^debug_toolbar', '^rosetta']

####### Selenium tests config ########

SELENIUM_SETUP = {
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

INTERNAL_DATA = {
    "business_unit": [],
    "product": ["CommCare", "CommConnect", "CommTrack", "RapidSMS", "Custom"],
    "services": [],
    "account_types": [],
    "initiatives": [],
    "contract_type": [],
    "area": [
        {
        "name": "Health",
        "sub_areas": ["Maternal, Newborn, & Child Health", "Family Planning", "HIV/AIDS"]
        },
        {
        "name": "Other",
        "sub_areas": ["Emergency Response"]
        },
    ],
    "country": ["Afghanistan", "Albania", "Algeria", "Andorra", "Angola", "Antigua & Deps", "Argentina", "Armenia",
                "Australia", "Austria", "Azerbaijan", "Bahamas", "Bahrain", "Bangladesh", "Barbados", "Belarus",
                "Belgium", "Belize", "Benin", "Bhutan", "Bolivia", "Bosnia Herzegovina", "Botswana", "Brazil",
                "Brunei", "Bulgaria", "Burkina", "Burundi", "Cambodia", "Cameroon", "Canada", "Cape Verde",
                "Central African Rep", "Chad", "Chile", "China", "Colombia", "Comoros", "Congo",
                "Congo {Democratic Rep}", "Costa Rica", "Croatia", "Cuba", "Cyprus", "Czech Republic", "Denmark",
                "Djibouti", "Dominica", "Dominican Republic", "East Timor", "Ecuador", "Egypt", "El Salvador",
                "Equatorial Guinea", "Eritrea", "Estonia", "Ethiopia", "Fiji", "Finland", "France", "Gabon", "Gambia",
                "Georgia", "Germany", "Ghana", "Greece", "Grenada", "Guatemala", "Guinea", "Guinea-Bissau", "Guyana",
                "Haiti", "Honduras", "Hungary", "Iceland", "India", "Indonesia", "Iran", "Iraq", "Ireland {Republic}",
                "Israel", "Italy", "Ivory Coast", "Jamaica", "Japan", "Jordan", "Kazakhstan", "Kenya", "Kiribati",
                "Korea North", "Korea South", "Kosovo", "Kuwait", "Kyrgyzstan", "Laos", "Latvia", "Lebanon", "Lesotho",
                "Liberia", "Libya", "Liechtenstein", "Lithuania", "Luxembourg", "Macedonia", "Madagascar", "Malawi",
                "Malaysia", "Maldives", "Mali", "Malta", "Marshall Islands", "Mauritania", "Mauritius", "Mexico",
                "Micronesia", "Moldova", "Monaco", "Mongolia", "Montenegro", "Morocco", "Mozambique", "Myanmar, {Burma}",
                "Namibia", "Nauru", "Nepal", "Netherlands", "New Zealand", "Nicaragua", "Niger", "Nigeria", "Norway",
                "Oman", "Pakistan", "Palau", "Panama", "Papua New Guinea", "Paraguay", "Peru", "Philippines", "Poland",
                "Portugal", "Qatar", "Romania", "Russian Federation", "Rwanda", "St Kitts & Nevis", "St Lucia",
                "Saint Vincent & the Grenadines", "Samoa", "San Marino", "Sao Tome & Principe", "Saudi Arabia",
                "Senegal", "Serbia", "Seychelles", "Sierra Leone", "Singapore", "Slovakia", "Slovenia",
                "Solomon Islands", "Somalia", "South Africa", "South Sudan", "Spain", "Sri Lanka", "Sudan", "Suriname",
                "Swaziland", "Sweden", "Switzerland", "Syria", "Taiwan", "Tajikistan", "Tanzania", "Thailand", "Togo",
                "Tonga", "Trinidad & Tobago", "Tunisia", "Turkey", "Turkmenistan", "Tuvalu", "Uganda", "Ukraine",
                "United Arab Emirates", "United Kingdom", "United States", "Uruguay", "Uzbekistan", "Vanuatu",
                "Vatican City", "Venezuela", "Vietnam", "Yemen", "Zambia", "Zimbabwe"]
}
