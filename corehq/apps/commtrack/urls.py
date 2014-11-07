#from django.conf.urls.defaults import patterns, url
from django.conf.urls.defaults import *
from corehq.apps.commtrack.views import (
    ProgramListView, FetchProgramListView, NewProgramView, EditProgramView,
    FetchProductForProgramListView, DefaultConsumptionView,
    SMSSettingsView, CommTrackSettingsView
)

urlpatterns = patterns('corehq.apps.commtrack.views',
    url(r'^api/supply_point_query/$', 'api_query_supply_point'),
)

# used in settings urls
settings_urls = patterns('corehq.apps.commtrack.views',
    url(r'^$', 'default', name="default_commtrack_setup"),
    url(r'^project_settings/$', CommTrackSettingsView.as_view(), name=CommTrackSettingsView.urlname),
    url(r'^programs/$', ProgramListView.as_view(), name=ProgramListView.urlname),
    url(r'^programs/list/$', FetchProgramListView.as_view(), name=FetchProgramListView.urlname),
    url(r'^programs/new/$', NewProgramView.as_view(), name=NewProgramView.urlname),
    url(r'^programs/(?P<prog_id>[\w-]+)/$', EditProgramView.as_view(), name=EditProgramView.urlname),
    url(r'^programs/(?P<prog_id>[\w-]+)/productlist/$', FetchProductForProgramListView.as_view(),
        name=FetchProductForProgramListView.urlname),
    url(r'^delete/(?P<prog_id>[\w-]+)/$', 'delete_program', name='delete_program'),
    url(r'^default_consumption/$', DefaultConsumptionView.as_view(), name=DefaultConsumptionView.urlname),
    url(r'^sms/$', SMSSettingsView.as_view(), name=SMSSettingsView.urlname),
)
