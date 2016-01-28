from dev_settings import *

####### Database config. This assumes Postgres #######
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'commcarehq',
        'USER': 'commcarehq',
        'PASSWORD': 'commcarehq',
        'HOST': 'postgres',
        'PORT': '5432',
        'TEST': {
            'SERIALIZE': False,
        },
    },
}

def get_partitioned_database_config(use_partitioned_db):
    """
    PARTITION_DATABASE_CONFIG = get_partitioned_database_config(USE_PARTITIONED_DATABASE)
    """
    if not use_partitioned_db:
        return

    global DATABASES

    DATABASES.update({
        'proxy': {
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'NAME': 'commcarehq_proxy',
            'USER': 'commcarehq',
            'PASSWORD': 'commcarehq',
            'HOST': 'postgres',
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
            'HOST': 'postgres',
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
            'HOST': 'postgres',
            'PORT': '5432',
            'TEST': {
                'SERIALIZE': False,
            },
        },
    })

    return {
        'shards': {
            'p1': [0, 1],
            'p2': [2, 3]
        },
        'groups': {
            'main': ['default'],
            'proxy': ['proxy'],
            'form_processing': ['p1', 'p2'],
        },
        'host_map': {
            'postgres': 'localhost'
        }
    }

####### Couch Config ######
COUCH_HTTPS = False
COUCH_SERVER_ROOT = 'couch:5984'
COUCH_USERNAME = ''
COUCH_PASSWORD = ''
COUCH_DATABASE_NAME = 'commcarehq'

redis_cache = {
    'BACKEND': 'django_redis.cache.RedisCache',
    'LOCATION': 'redis://redis:6379/0',
    'OPTIONS': {},
}
CACHES = {
    'default': redis_cache,
    'redis': redis_cache
}

ELASTICSEARCH_HOST = 'elasticsearch'
ELASTICSEARCH_PORT = 9200

SHARED_DRIVE_ROOT = '/sharedfiles'

# S3_BLOB_DB_SETTINGS = {"url": "http://moto:5000"}
