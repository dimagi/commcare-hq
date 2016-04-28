from .dockersettings import *

import sys

ADMINS = (('Admin', 'commcare-admin@bandim.org'),)

AUDIT_ADMIN_VIEWS=False

SEND_BROKEN_LINK_EMAILS = True
CELERY_SEND_TASK_ERROR_EMAILS = True

CELERY_PERIODIC_QUEUE = 'celery' # change this to something else if you want a different queue for periodic tasks

CELERY_RESULT_BACKEND = 'djcelery.backends.database:DatabaseBackend'

CELERY_FLOWER_URL = 'http://celery:5555'
BROKER_URL = 'amqp://guest:guest@rabbit:5672/commcarehq'

LESS_DEBUG = False
LESS_WATCH = False

COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True

DEBUG = False
TEMPLATE_DEBUG = DEBUG

BITLY_LOGIN = None

XFORMS_PLAYER_URL = 'http://127.0.0.1:4444'

TOUCHFORMS_API_USER = 'admin@example.com'
TOUCHFORMS_API_PASSWORD = 'password'

DEFAULT_PROTOCOL = "https"  # or https

BASE_ADDRESS = "bissau.bandim.org:443"

CCHQ_API_THROTTLE_REQUESTS = 200
CCHQ_API_THROTTLE_TIMEFRAME = 10

PHONE_TIMEZONES_HAVE_BEEN_PROCESSED = True
PHONE_TIMEZONES_SHOULD_BE_PROCESSED = True

TESTS_SHOULD_TRACK_CLEANLINESS = True

RESTORE_PAYLOAD_DIR_NAME = 'restore'
SHARED_TEMP_DIR_NAME = 'temp'

ENABLE_PRELOGIN_SITE = True

KAFKA_URL = 'kafka:9092'
SHARED_DRIVE_ROOT = '/mnt/sharedfiles'
#EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
EMAIL_LOGIN = "commcare-admin@bandim.org"
EMAIL_PASSWORD = "xxxxxxx"
EMAIL_SMTP_HOST = "mail.bandim.org"
EMAIL_SMTP_PORT = 587
# These are the normal Django settings
EMAIL_USE_TLS = False

SERVER_EMAIL = 'commcarehq-admin@bandim.org' #the physical server emailing - differentiate if needed
DEFAULT_FROM_EMAIL = 'commcarehq-admin@bandim.org'
SUPPORT_EMAIL = "commcarehq-admin@bandim.org"
EMAIL_SUBJECT_PREFIX = '[bandim-commcarehq] '


