from .dockersettings import *

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

ADMINS = (('Admin', 'commcare-admin@bandim.org'),)

AUDIT_ADMIN_VIEWS=False

SEND_BROKEN_LINK_EMAILS = True
CELERY_SEND_TASK_ERROR_EMAILS = True

CELERY_PERIODIC_QUEUE = 'celery' # change this to something else if you want a different queue for periodic tasks

CELERY_RESULT_BACKEND = 'djcelery.backends.database:DatabaseBackend'

CELERY_FLOWER_URL = 'http://celery:5555'
BROKER_URL = 'amqp://guest:guest@rabbit:5672/commcarehq'

LESS_DEBUG = True
LESS_WATCH = False
COMPRESS_OFFLINE = False

BITLY_LOGIN = None

XFORMS_PLAYER_URL = 'http://127.0.0.1:4444'

TOUCHFORMS_API_USER = 'admin@example.com'
TOUCHFORMS_API_PASSWORD = 'password'

BASE_ADDRESS = '{}:8000'.format(os.environ.get('BASE_HOST', 'localhost'))

CCHQ_API_THROTTLE_REQUESTS = 200
CCHQ_API_THROTTLE_TIMEFRAME = 10

PHONE_TIMEZONES_HAVE_BEEN_PROCESSED = True
PHONE_TIMEZONES_SHOULD_BE_PROCESSED = True

TESTS_SHOULD_TRACK_CLEANLINESS = True

RESTORE_PAYLOAD_DIR_NAME = 'restore'
SHARED_TEMP_DIR_NAME = 'temp'

ENABLE_PRELOGIN_SITE = True

KAFKA_URL = 'kafka:9092'
SHARED_DRIVE_ROOT = '/sharedfiles'

ENVIRONMENT_HOSTS = {"celery": ["celery"], "all": ["localhost"], "zookeeper": ["kafka"], "postgresql": ["postgresql"], "couchdb": ["couchdb"], "redis": ["redis"], "rabbitmq": ["rabbit"], "kafka": ["kafka"], "ungrouped": [], "webworkers": ["192.168.33.21"], "elasticsearch": ["elasticsearch"], "pillowtop": ["localhost"], "touchforms": ["localhost"], "shared_dir_host": ["localhost"]}

