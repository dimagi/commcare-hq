from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url
from corehq.apps.commtrack.views import (
    DefaultConsumptionView, SMSSettingsView, CommTrackSettingsView,
    StockLevelsView, RebuildStockStateView,
    default,
)

# used in settings urls
settings_urls = [
    url(r'^$', default, name="default_commtrack_setup"),
    url(r'^project_settings/$', CommTrackSettingsView.as_view(), name=CommTrackSettingsView.urlname),
    url(r'^default_consumption/$', DefaultConsumptionView.as_view(), name=DefaultConsumptionView.urlname),
    url(r'^sms/$', SMSSettingsView.as_view(), name=SMSSettingsView.urlname),
    url(r'^stock_levels/$', StockLevelsView.as_view(), name=StockLevelsView.urlname),
    url(r'^rebuild_stock_state/$', RebuildStockStateView.as_view(),
        name=RebuildStockStateView.urlname),
]
