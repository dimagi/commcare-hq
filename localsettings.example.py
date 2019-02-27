from __future__ import absolute_import
from __future__ import unicode_literals
import os

INTERNAL_IPS = ['127.0.0.1']

####### Database config. This assumes Postgres #######

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'commcarehq',
        'USER': 'commcarehq',
        'PASSWORD': 'commcarehq',
        'HOST': 'localhost',
        'PORT': '5432',
        'TEST': {
            'SERIALIZE': False,
        },
    }
}

SYNCLOGS_SQL_DB_ALIAS = 'default'

USE_PARTITIONED_DATABASE = False

if USE_PARTITIONED_DATABASE:

    PARTITION_DATABASE_CONFIG = {
        'shards': {
            'p1': [0, 1],
            'p2': [2, 3]
        },
        'groups': {
            'main': ['default'],
            'proxy': ['proxy'],
            'form_processing': ['p1', 'p2'],
        },
        'host_map': {}  # allows mapping HOST in DATABASE settings to a different value for plproxy
    }

    DATABASES.update({
        'proxy': {
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'NAME': 'commcarehq_proxy',
            'USER': 'commcarehq',
            'PASSWORD': 'commcarehq',
            'HOST': 'localhost',
            'PORT': '5432',
            'TEST': {
                'SERIALIZE': False,
            },
        },
        'p1': {
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'NAME': 'commcarehq_p1',
            'USER': 'commcarehq',
            'PASSWORD': 'commcarehq',
            'HOST': 'localhost',
            'PORT': '5432',
            'TEST': {
                'SERIALIZE': False,
            },
        },
        'p2': {
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'NAME': 'commcarehq_p2',
            'USER': 'commcarehq',
            'PASSWORD': 'commcarehq',
            'HOST': 'localhost',
            'PORT': '5432',
            'TEST': {
                'SERIALIZE': False,
            },
        },
    })

####### Couch Config ######
COUCH_DATABASES = {
    'default': {
        'COUCH_HTTPS': False,
        'COUCH_SERVER_ROOT': '127.0.0.1:5984',
        'COUCH_USERNAME': 'commcarehq',
        'COUCH_PASSWORD': '',
        'COUCH_DATABASE_NAME': 'commcarehq',
    },
}

### Public / Pre-login Site information
ENABLE_PRELOGIN_SITE = False

####### # Email setup ########
# email settings: these ones are the custom hq ones
EMAIL_LOGIN = "notifications@example.com"
EMAIL_PASSWORD = "******"
EMAIL_SMTP_HOST = "smtp.gmail.com"
EMAIL_SMTP_PORT = 587

# Print emails to console so there is no danger of spamming, but you can still get registration URLs
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

ADMINS = (('HQ Dev Team', 'commcarehq-dev+www-notifications@example.com'),)
BUG_REPORT_RECIPIENTS = ['commcarehq-support@example.com']
NEW_DOMAIN_RECIPIENTS = ['commcarehq-dev+newdomain@example.com']
EXCHANGE_NOTIFICATION_RECIPIENTS = ['commcarehq-dev+exchange@example.com']

SERVER_EMAIL = 'commcarehq-noreply@example.com'  # the physical server emailing - differentiate if needed
DEFAULT_FROM_EMAIL = 'commcarehq-noreply@example.com'
SUPPORT_EMAIL = "commcarehq-support@example.com"
EMAIL_SUBJECT_PREFIX = '[commcarehq] '
SERVER_ENVIRONMENT = 'changeme' #Modify this value if you are deploying multiple environments of HQ to the same machine. Identify the target type of this running environment

####### Log/debug setup ########

DEBUG = True

# log directories must exist and be writeable!
DJANGO_LOG_FILE = "/tmp/commcare-hq.django.log"
LOG_FILE = "/tmp/commcare-hq.log"
SHARED_DRIVE_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sharedfiles")

CELERY_PERIODIC_QUEUE = 'celery' # change this to something else if you want a different queue for periodic tasks
CELERY_FLOWER_URL = 'http://127.0.0.1:5555'

####### Less/Django Compressor ########

LESS_DEBUG = True
COMPRESS_ENABLED = False
COMPRESS_OFFLINE = False

####### Bitly ########

BITLY_LOGIN = None  # set to None to disable bitly app url shortening (useful offline) set to 'dimagi' if you are using the api key
BITLY_APIKEY = '*******'


####### Jar signing config ########

_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
# Uncomment below when signing the JAR
# JAR_SIGN = {
#     'key_store': os.path.join(os.path.dirname(os.path.dirname(_ROOT_DIR)), "DimagiKeyStore"),
#     'key_alias': "javarosakey",
#     'store_pass': "*******",
#     'key_pass': "*******",
# }

####### Touchforms config - for CloudCare #######

XFORMS_PLAYER_URL = 'http://127.0.0.1:4444'

# email and password for an admin django user, such as one created with
# ./manage.py make_superuser <email>
TOUCHFORMS_API_USER = 'admin@example.com'
TOUCHFORMS_API_PASSWORD = 'password'


####### Misc / HQ-specific Config ########

DEFAULT_PROTOCOL = "http"  # or https
OVERRIDE_LOCATION = "https://www.commcarehq.org"

# Set to something like "192.168.1.5:8000" (with your IP address).
# See corehq/apps/builds/README.md for more information.
BASE_ADDRESS = 'localhost:8000'

# Set your analytics IDs here for GA and pingdom RUM
ANALYTICS_IDS = {
    'GOOGLE_ANALYTICS_API_ID': '',
    'KISSMETRICS_KEY': '',
    'HUBSPOT_API_KEY': '',
    'FULLSTORY_ID': '',
}

ANALYTICS_CONFIG = {
    "HQ_INSTANCE": '',  # e.g. "www", or "india", or "staging"
    "DEBUG": DEBUG,
    "LOG_LEVEL": "debug",   # "warning", "debug", "verbose", or "" for no logging
}

# Green house api key
GREENHOUSE_API_KEY = ''

AXES_LOCK_OUT_AT_FAILURE = False
LUCENE_ENABLED = True

PREVIEWER_RE = r'^.*@dimagi\.com$'

GMAPS_API_KEY = '******'
MAPS_LAYERS = {
    'Maps': {
        'family': 'mapbox',
        'args': {
            'apikey': '*****'
        }
    },
    'Satellite': {
        'family': 'mapbox',
        'args': {
            'apikey': '*****'
        }
    },
}

FORMTRANSLATE_TIMEOUT = 5
LOCAL_APPS = (
#    'django_coverage', # Adds `python manage.py test_coverage` (settings below)
#    'debug_toolbar',   # Adds a retractable panel to every page giving profiling & debugging info
#    'devserver',       # Adds improved dev server that also prints SQL on the console (for AJAX, etc, when you cannot use debug_toolbar)
#    'django_cpserver', # Another choice for a replacement server
#    'dimagi.utils',
#    'testapps.test_elasticsearch',
#    'testapps.test_pillowtop',
)

LOCAL_MIDDLEWARE = [
    # 'debug_toolbar.middleware.DebugToolbarMiddleware',
]

# list of domains to enable ADM reporting on
ADM_ENABLED_PROJECTS = []

# prod settings
SOIL_DEFAULT_CACHE = "redis"

# reports cache
REPORT_CACHE = 'default'  # or e.g. 'redis'

redis_cache = {
    'BACKEND': 'django_redis.cache.RedisCache',
    'LOCATION': 'redis://127.0.0.1:6379/0',
    'OPTIONS': {
        'PICKLE_VERSION': 2,  # After PY3 migration: remove
    },
}
# example redis cluster setting
redis_cluster_cache = {
    'BACKEND': 'django_redis.cache.RedisCache',
    'LOCATION': 'redis://127.0.0.1:6379/0',
    'OPTIONS': {
        'REDIS_CLIENT_CLASS': 'rediscluster.RedisCluster',
        'CONNECTION_POOL_CLASS': 'rediscluster.connection.ClusterConnectionPool',
        'CONNECTION_POOL_KWARGS': {
            'skip_full_coverage_check': True
        },
        'PICKLE_VERSION': 2,  # After PY3 migration: remove
    }
}
CACHES = {
    'default': redis_cache,
    'redis': redis_cache,
}

# on both a local and a distributed environment this should be localhost
ELASTICSEARCH_HOST = 'localhost'
ELASTICSEARCH_PORT = 9200

LOCAL_PILLOWTOPS = {
#    'my_pillows': ['some.pillow.Class', ],
#    'and_more': []
}

####### API throttling #####

CCHQ_API_THROTTLE_REQUESTS = 200  # number of requests allowed per timeframe
                                  # Use a lower value in production. This is set
                                  # to 200 to prevent AssertionError: 429 != 200
                                  # test failures in development environsments.
CCHQ_API_THROTTLE_TIMEFRAME = 10  # seconds

####### django-coverage config ########

COVERAGE_REPORT_HTML_OUTPUT_DIR='coverage-html'
COVERAGE_MODULE_EXCLUDES= ['tests$', 'settings$', 'urls$', 'locale$',
                           'common.views.test', '^django', 'management', 'migrations',
                           '^south', '^debug_toolbar']

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

# The passcodes will print out on the console
# TWO_FACTOR_CALL_GATEWAY = 'two_factor.gateways.fake.Fake'
# TWO_FACTOR_SMS_GATEWAY = 'two_factor.gateways.fake.Fake'
