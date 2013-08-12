#from django.conf.urls.defaults import patterns, url
from django.conf.urls.defaults import *
from corehq.apps.locations.views import LocationsListView, NewLocationView, EditLocationView

settings_urls = patterns('corehq.apps.locations.views',
    url(r'^$', LocationsListView.as_view(), name=LocationsListView.name),
    url(r'^sync_facilities/$', 'sync_facilities', name='sync_facilities_with_locations'),
    url(r'^new/$', NewLocationView.as_view(), name=NewLocationView.name),
    url(r'^(?P<loc_id>[\w-]+)/$', EditLocationView.as_view(), name=EditLocationView.name),
)
