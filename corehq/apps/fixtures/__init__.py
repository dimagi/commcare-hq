from corehq.preindex import ExtraPreindexPlugin
from django.conf import settings

ExtraPreindexPlugin.register('fixtures', __file__, settings.NEW_FIXTURES_DB)
