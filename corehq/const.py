from __future__ import unicode_literals
USER_DATETIME_FORMAT = "%b %d, %Y %H:%M %Z"
USER_DATETIME_FORMAT_WITH_SEC = "%b %d, %Y %H:%M:%S %Z"

USER_DATE_FORMAT = "%b %d, %Y"
USER_TIME_FORMAT = "%H:%M %Z"
USER_MONTH_FORMAT = "%B %Y"

SERVER_DATE_FORMAT = "%Y-%m-%d"
SERVER_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
SERVER_DATETIME_FORMAT_NO_SEC = "%Y-%m-%d %H:%M"


MISSING_APP_ID = '_MISSING_APP_ID'

OPENROSA_VERSION_1 = "1.0"
OPENROSA_VERSION_2 = "2.0"
OPENROSA_VERSION_3 = "3.0"
OPENROSA_VERSION_2_1 = "2.1"
OPENROSA_DEFAULT_VERSION = OPENROSA_VERSION_1
OPENROSA_VERSION_MAP = {
    'ASYNC_RESTORE': OPENROSA_VERSION_2,
    # Indexed fixture also applies when OR version not specified
    'INDEXED_PRODUCTS_FIXTURE': OPENROSA_VERSION_2_1,
}

GOOGLE_PLAY_STORE_COMMCARE_URL = 'https://play.google.com/store/apps/details?id=org.commcare.dalvik&hl=en'

ONE_DAY = 60 * 60 * 24
