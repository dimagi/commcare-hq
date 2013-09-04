import os

####### Configuration for CommCareHQ Running on Travis-CI #####

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

SQL_REPORTING_DATABASE_URL = "sqlite:////tmp/commcare_reporting_test.db"

####### Couch Config ######
COUCH_HTTPS = False 
COUCH_SERVER_ROOT = '127.0.0.1:5984' 
COUCH_USERNAME = 'commcarehq'
COUCH_PASSWORD = 'not-a-real-password'
COUCH_DATABASE_NAME = 'commcarehq'

######## Email setup ########
# email settings: these ones are the custom hq ones
EMAIL_LOGIN = "notifications@dimagi.com"
EMAIL_PASSWORD = "******"
EMAIL_SMTP_HOST = "smtp.gmail.com"
EMAIL_SMTP_PORT = 587
EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend'

####### Bitly ########

BITLY_LOGIN = 'dimagi'
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

ELASTICSEARCH_HOST = 'localhost' 
ELASTICSEARCH_PORT = 9200

AUDIT_ADMIN_VIEWS=False

# No logging
LOGGING = {
    'version': 1,
    'handlers': {
        'null': {
            'level': 'DEBUG',
            'class': 'django.utils.log.NullHandler',
        },
    },
    'loggers': {
        '': {
            'level': 'CRITICAL',
            'handler': 'null',
            'propagate': False,
        }
    }
}
