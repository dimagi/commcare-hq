from django.conf.urls.defaults import patterns, url
from corehq.apps.commtrack.views import (
    DefaultConsumptionView, SMSSettingsView, CommTrackSettingsView
)

urlpatterns = patterns('corehq.apps.commtrack.views',
    url(r'^api/supply_point_query/$', 'api_query_supply_point'),
)

# used in settings urls
settings_urls = patterns('corehq.apps.commtrack.views',
    url(r'^$', 'default', name="default_commtrack_setup"),
    url(r'^project_settings/$', CommTrackSettingsView.as_view(), name=CommTrackSettingsView.urlname),
    url(r'^default_consumption/$', DefaultConsumptionView.as_view(), name=DefaultConsumptionView.urlname),
    url(r'^sms/$', SMSSettingsView.as_view(), name=SMSSettingsView.urlname),
)
