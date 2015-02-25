from corehq.preindex import CouchAppsPreindexPlugin
from django.conf import settings

CouchAppsPreindexPlugin.register('mvp_indicators', __file__, {
    'mvp_births_indicators': settings.MVP_INDICATOR_DB,
    'mvp_child_health_indicators': settings.MVP_INDICATOR_DB,
    'mvp_chw_referrals_indicators': settings.MVP_INDICATOR_DB,
    'mvp_chw_visits_indicators': settings.MVP_INDICATOR_DB,
    'mvp_deaths_indicators': settings.MVP_INDICATOR_DB,
    'mvp_maternal_health_indicators': settings.MVP_INDICATOR_DB,
    'mvp_over5_indicators': settings.MVP_INDICATOR_DB,
    'mvp_verbal_autopsy_indicators': settings.MVP_INDICATOR_DB,
})
