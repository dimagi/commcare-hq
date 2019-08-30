from django.conf import settings

from corehq.preindex import ExtraPreindexPlugin

ExtraPreindexPlugin.register('domain', __file__, (
    settings.NEW_DOMAINS_DB,
    settings.NEW_USERS_GROUPS_DB,
    settings.NEW_FIXTURES_DB,
    'meta',
))

SHARED_DOMAIN = "<shared>"
UNKNOWN_DOMAIN = "<unknown>"
