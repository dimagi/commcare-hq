from corehq.preindex import ExtraPreindexPlugin
from django.conf import settings


ExtraPreindexPlugin('commtrack', __file__, (None, settings.NEW_CASES_DB))
