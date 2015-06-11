"""
This is a home for shared dev settings.  Feel free to add anything that all
devs should have set.

Add `from dev_settings import *` to the top of your localsettings file to use.
You can then override or append to any of these settings there.
"""

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
    ('corehq.apps.users.models', ('CommCareUser', 'CommCareCase')),
    ('couchforms.models', 'XFormInstance'),

    # Data querying utils
    ('dimagi.utils.couch.database', 'get_db'),
    ('corehq.apps.sofabed.models', ('FormData', 'CaseData')),
    ('corehq.apps.es', '*'),
)

ALLOWED_HOSTS = ['*']
FIX_LOGGER_ERROR_OBFUSCATION = True
