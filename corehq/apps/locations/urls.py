#from django.conf.urls.defaults import patterns, url
from django.conf.urls.defaults import *
from corehq.apps.locations.views import (
    LocationsListView,
    NewLocationView,
    EditLocationView,
    FacilitySyncView,
    LocationImportView,
    LocationImportStatusView,
    LocationSettingsView,
    ILSFacilitySyncView)

settings_urls = patterns('corehq.apps.locations.views',
    url(r'^$', 'default', name='default_locations_view'),
    url(r'^list/$', LocationsListView.as_view(), name=LocationsListView.urlname),
    url(r'^location_settings/$', LocationSettingsView.as_view(), name=LocationSettingsView.urlname),
    url(r'^sync_facilities/$', FacilitySyncView.as_view(), name=FacilitySyncView.urlname),
    url(r'^sync_facilities_ils/$', ILSFacilitySyncView.as_view(), name=ILSFacilitySyncView.urlname),
    url(r'^sync_facilities_async/$', 'sync_facilities', name='sync_facilities_with_locations'),
    url(r'^import/$', LocationImportView.as_view(), name=LocationImportView.urlname),
    url(r'^import_status/(?P<download_id>[0-9a-fA-Z]{25,32})/$', LocationImportStatusView.as_view(), name=LocationImportStatusView.urlname),
    url(r'^location_importer_job_poll/(?P<download_id>[0-9a-fA-Z]{25,32})/$',
        'location_importer_job_poll', name='location_importer_job_poll'),
    url(r'^export_locations/$', 'location_export', name='location_export'),
    url(r'^sync_openlmis/$', 'sync_openlmis', name='sync_openlmis'),
    url(r'^sync_ilsgateway/$', 'sync_ilsgateway', name='sync_ilsgateway'),
    url(r'^new/$', NewLocationView.as_view(), name=NewLocationView.urlname),
    url(r'^(?P<loc_id>[\w-]+)/$', EditLocationView.as_view(), name=EditLocationView.urlname),
)
