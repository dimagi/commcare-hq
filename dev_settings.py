"""
This is a home for shared dev settings.  Feel free to add anything that all
devs should have set.

Add `from dev_settings import *` to the top of your localsettings file to use.
You can then override or append to any of these settings there.
"""
import os

LOCAL_APPS = (
    'django_extensions',
)

####### Django Extensions #######
# These things will be imported when you run ./manage.py shell_plus
SHELL_PLUS_POST_IMPORTS = (
    # Models
    ('corehq.apps.domain.models', 'Domain'),
    ('corehq.apps.groups.models', 'Group'),
    ('corehq.apps.locations.models', 'Location'),
    ('corehq.apps.users.models', ('CouchUser', 'WebUser', 'CommCareUser')),
    ('casexml.apps.case.models', 'CommCareCase'),
    ('couchforms.models', 'XFormInstance'),

    # Data querying utils
    ('dimagi.utils.couch.database', 'get_db'),
    ('corehq.apps.sofabed.models', ('FormData', 'CaseData')),
    ('corehq.apps.es', '*'),
)

ALLOWED_HOSTS = ['*']
FIX_LOGGER_ERROR_OBFUSCATION = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'commcarehq',
        'USER': 'commcarehq',
        'PASSWORD': 'commcarehq',
        'HOST': 'localhost',
        'PORT': '5432'
    }
}

BOWER_PATH = os.popen('which bower').read().strip()

CACHES = {'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}}


PILLOWTOP_MACHINE_ID = 'testhq'  # for tests

#  make celery synchronous
CELERY_ALWAYS_EAGER = True
# Fail hard in tasks so you get a traceback
CELERY_EAGER_PROPAGATES_EXCEPTIONS = True
