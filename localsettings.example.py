from dev_settings import *

####### Database config #######

USE_PARTITIONED_DATABASE = False

# example partitioned DB set up
if USE_PARTITIONED_DATABASE:

    DATABASES.update({
        'proxy': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'commcarehq_proxy',
            'USER': 'commcarehq',
            'PASSWORD': 'commcarehq',
            'HOST': 'localhost',
            'PORT': '5432',
            'TEST': {
                'SERIALIZE': False,
            },
            'PLPROXY': {
                'PROXY': True
            }
        },
        'p1': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'commcarehq_p1',
            'USER': 'commcarehq',
            'PASSWORD': 'commcarehq',
            'HOST': 'localhost',
            'PORT': '5432',
            'TEST': {
                'SERIALIZE': False,
            },
            'PLPROXY': {
                'SHARDS': [0, 1],
            }
        },
        'p2': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'commcarehq_p2',
            'USER': 'commcarehq',
            'PASSWORD': 'commcarehq',
            'HOST': 'localhost',
            'PORT': '5432',
            'TEST': {
                'SERIALIZE': False,
            },
            'PLPROXY': {
                'SHARDS': [2, 3],
            }
        },
    })


# Modify this value if you are deploying multiple environments of HQ to the same machine.
# Identify the target type of this running environment
SERVER_ENVIRONMENT = 'changeme'

####### Less/Django Compressor ########

COMPRESS_ENABLED = False
COMPRESS_OFFLINE = False

####### Misc / HQ-specific Config ########

# Set to something like "192.168.1.5:8000" (with your IP address) to enable submitting
# data to your local environment from an android phone.
# See corehq/apps/builds/README.md for more information.
BASE_ADDRESS = 'localhost:8000'

PREVIEWER_RE = r'^.*@dimagi\.com$'

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

LOCAL_APPS += (
#    'debug_toolbar',   # Adds a retractable panel to every page giving profiling & debugging info
)

LOCAL_MIDDLEWARE = [
    # 'debug_toolbar.middleware.DebugToolbarMiddleware',
]

LOCAL_PILLOWTOPS = {
#    'my_pillows': ['some.pillow.Class', ],
#    'and_more': []
}
