from django.conf import settings

from corehq.preindex import ExtraPreindexPlugin

ExtraPreindexPlugin.register('fixtures', __file__, settings.NEW_FIXTURES_DB)
