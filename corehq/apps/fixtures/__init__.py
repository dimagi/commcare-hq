from django.conf import settings

from corehq.preindex import ExtraPreindexPlugin

ExtraPreindexPlugin.register('fixtures', __file__, settings.FIXTURES_DB)
