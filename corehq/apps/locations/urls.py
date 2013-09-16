#from django.conf.urls.defaults import patterns, url
from django.conf.urls.defaults import *
from corehq.apps.locations.views import LocationsListView, NewLocationView, EditLocationView, FacilitySyncView

settings_urls = patterns('corehq.apps.locations.views',
    url(r'^$', 'default', name='default_locations_view'),
    url(r'^list/$', LocationsListView.as_view(), name=LocationsListView.urlname),
    url(r'^sync_facilities/$', FacilitySyncView.as_view(), name=FacilitySyncView.urlname),
    url(r'^sync_facilities_async/$', 'sync_facilities', name='sync_facilities_with_locations'),
    url(r'^new/$', NewLocationView.as_view(), name=NewLocationView.urlname),
    url(r'^(?P<loc_id>[\w-]+)/$', EditLocationView.as_view(), name=EditLocationView.urlname),
)
