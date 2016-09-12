import logging.handlers
import sys
import os

# TODO how to harmonize this with django settings?

# allow cross-origin requests to touchforms daemon. if false, all access to
# daemon must be proxied through the django web server
ALLOW_CROSS_ORIGIN = False

# whether to save interim sessions so that they may be recovered after a
# daemon restart
PERSIST_SESSIONS = True
PERSISTENCE_DIRECTORY = None  # defaults to /tmp

# you can add extensions using this
EXTENSION_MODULES = [
    'handlers.static',  # support for static functions and static date functions
]

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# postgres peristence stuff
USES_POSTGRES = False
POSTGRES_JDBC_JAR = os.path.join(BASE_DIR, "jrlib/postgresql-9.4-1201.jdbc41.jar")

# sqlite persistence stuff

SQLITE_DBS_DIRECTORY = "%s/dbs" % BASE_DIR

# be more forgiving about data types in api
HACKS_MODE = True

# base url for touchcare api queries
URL_HOST = "{{HOST}}"
URL_ROOT = URL_HOST + "/a/{{ DOMAIN }}"

POSTGRES_DATABASE = {
    'HOST': 'localhost',
    'PORT': '5432',
    'NAME': 'hqdev',
    'USER': 'django',
    'PASSWORD': 'django',
    'SSL': True,
    'PREPARE_THRESHOLD': 0
}

### LOGGING VARIABLES ###
FORMPLAYER_LOG_FILE = 'formplayer-dev.log'
DATADOG_FORMPLAYER_LOG_FILE = 'datadog-formplayer-dev.log'

formats = {
    'verbose': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s',
    'datadog': 'touchforms.%(metric)s %(timestamp)s %(value)s metric_type=%(metric_type)s %(message)s'
}
### END LOGGING VARIABLES ###


try:
    from localsettings import *
except ImportError:
    pass

### LOGGING CONFIG ###
formatter = logging.Formatter(formats['verbose'])
datadog_formatter = logging.Formatter(formats['datadog'])

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format=formats['verbose']
)

logger = logging.getLogger('formplayer')
datadog_logger = logging.getLogger('datadog')

rotatingHandler = logging.handlers.RotatingFileHandler(
    FORMPLAYER_LOG_FILE,
    maxBytes=50 * 1024 * 1024,
    backupCount=20,
)
rotatingHandler.setFormatter(formatter)
logger.addHandler(rotatingHandler)
logger.setLevel(logging.INFO)

datadogRotatingHandler = logging.handlers.RotatingFileHandler(
    DATADOG_FORMPLAYER_LOG_FILE,
    maxBytes=50 * 1024 * 1024,
    backupCount=20,
)
datadogRotatingHandler.setFormatter(datadog_formatter)
datadog_logger.addHandler(datadogRotatingHandler)
datadog_logger.setLevel(logging.INFO)

### END LOGGING CONFIG ###

CASE_API_URL = '%s/cloudcare/api/cases/' % URL_ROOT
FIXTURE_API_URL = '%s/cloudcare/api/fixtures' % URL_ROOT
LEDGER_API_URL = '%s/cloudcare/api/ledgers/' % URL_ROOT
RESTORE_URL = '%s/phone/restore/' % URL_ROOT

### Number of hours to sqlite Sqlite DBs without forcing a restore ###
SQLITE_STALENESS_WINDOW = 120
