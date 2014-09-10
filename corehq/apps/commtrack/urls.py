#from django.conf.urls.defaults import patterns, url
from django.conf.urls.defaults import *
from corehq.apps.commtrack.views import (
    ProductListView, FetchProductListView, NewProductView, EditProductView,
    ProgramListView, FetchProgramListView, NewProgramView, EditProgramView,
    FetchProductForProgramListView, DefaultConsumptionView, UploadProductView,
    ProductImportStatusView, SMSSettingsView, CommTrackSettingsView,
    ILSConfigView)

urlpatterns = patterns('corehq.apps.commtrack.views',
    url(r'^debug/bootstrap/$', 'bootstrap'),
    url(r'^debug/import_history/$', 'historical_import'),
    url(r'^debug/charts/$', 'charts'),
    url(r'^debug/location_dump/$', 'location_dump'),

    url(r'^api/supply_point_query/$', 'api_query_supply_point'),
)

# used in settings urls
settings_urls = patterns('corehq.apps.commtrack.views',
    url(r'^$', 'default', name="default_commtrack_setup"),
    url(r'^project_settings/$', CommTrackSettingsView.as_view(), name=CommTrackSettingsView.urlname),
    url(r'^products/$', ProductListView.as_view(), name=ProductListView.urlname),
    url(r'^products/list/$', FetchProductListView.as_view(), name=FetchProductListView.urlname),
    url(r'^products/new/$', NewProductView.as_view(), name=NewProductView.urlname),
    url(r'^products/upload/$', UploadProductView.as_view(), name=UploadProductView.urlname),
    url(r'^products/upload/status/(?P<download_id>[0-9a-fA-Z]{25,32})/$', ProductImportStatusView.as_view(),
        name=ProductImportStatusView.urlname),
    url(r'^products/upload/poll/(?P<download_id>[0-9a-fA-Z]{25,32})/$',
        'product_importer_job_poll', name='product_importer_job_poll'),
    url(r'^products/download/$', 'download_products', name='product_export'),
    url(r'^products/(?P<prod_id>[\w-]+)/$', EditProductView.as_view(), name=EditProductView.urlname),
    url(r'^programs/$', ProgramListView.as_view(), name=ProgramListView.urlname),
    url(r'^programs/list/$', FetchProgramListView.as_view(), name=FetchProgramListView.urlname),
    url(r'^programs/new/$', NewProgramView.as_view(), name=NewProgramView.urlname),
    url(r'^programs/(?P<prog_id>[\w-]+)/$', EditProgramView.as_view(), name=EditProgramView.urlname),
    url(r'^programs/(?P<prog_id>[\w-]+)/productlist/$', FetchProductForProgramListView.as_view(),
        name=FetchProductForProgramListView.urlname),
    url(r'^default_consumption/$', DefaultConsumptionView.as_view(), name=DefaultConsumptionView.urlname),
    url(r'^sms/$', SMSSettingsView.as_view(), name=SMSSettingsView.urlname),
    url(r'^ils_config/$', ILSConfigView.as_view(), name=ILSConfigView.urlname),
    url(r'^sync_ilsgateway/$', 'sync_ilsgateway', name='sync_ilsgateway'),
)
