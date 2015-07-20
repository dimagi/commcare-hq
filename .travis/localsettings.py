import os

####### Configuration for CommCareHQ Running on Travis-CI #####

BASE_ADDRESS = '127.0.0.1:8000'

####### Database config. This assumes Postgres ####### 
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'commcarehq',
        'USER': 'postgres',
        'PASSWORD': '',
        'HOST': 'localhost',
        'PORT': '5432'
    }
}

####### Couch Config ######
COUCH_HTTPS = False
COUCH_SERVER_ROOT = '127.0.0.1:5984'
COUCH_USERNAME = ''
COUCH_PASSWORD = ''
COUCH_DATABASE_NAME = 'commcarehq'

######## Email setup ########
# email settings: these ones are the custom hq ones
EMAIL_LOGIN = "notifications@dimagi.com"
EMAIL_PASSWORD = "******"
EMAIL_SMTP_HOST = "smtp.gmail.com"
EMAIL_SMTP_PORT = 587
EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend'

####### Bitly ########

BITLY_LOGIN = None
BITLY_APIKEY = '*******'


####### Jar signing config ########

_ROOT_DIR  = os.path.dirname(os.path.abspath(__file__))
JAR_SIGN = dict(
    jad_tool = os.path.join(_ROOT_DIR, "corehq", "apps", "app_manager", "JadTool.jar"),
    key_store = os.path.join(_ROOT_DIR, "InsecureTestingKeyStore"),
    key_alias = "javarosakey",
    store_pass = "onetwothreefourfive",
    key_pass = "onetwothreefourfive",
)

# prod settings
SOIL_DEFAULT_CACHE = "redis"
SOIL_BACKEND = "soil.CachedDownload"

redis_cache = {
    'BACKEND': 'redis_cache.cache.RedisCache',
    'LOCATION': 'localhost:6379:0',
    'OPTIONS': {},
}
CACHES = {
    'default': redis_cache,
    'redis': redis_cache
}

AUDIT_MODEL_SAVE = ['django.contrib.auth.models.User']

ELASTICSEARCH_HOST = 'localhost' 
ELASTICSEARCH_PORT = 9200

AUDIT_ADMIN_VIEWS=False

SECRET_KEY='secrettravis'

# No logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'phone.models': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    }
}

SOUTH_TESTS_MIGRATE = True
PHONE_TIMEZONES_HAVE_BEEN_PROCESSED = True
PHONE_TIMEZONES_SHOULD_BE_PROCESSED = True
