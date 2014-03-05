#from django.conf.urls.defaults import patterns, url
from django.conf.urls.defaults import *
from corehq.apps.commtrack.views import ProductListView, FetchProductListView, NewProductView, EditProductView, ProgramListView, FetchProgramListView, NewProgramView, EditProgramView, FetchProductForProgramListView, DefaultConsumptionView

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
    url(r'^products/$', ProductListView.as_view(), name=ProductListView.urlname),
    url(r'^products/list/$', FetchProductListView.as_view(), name=FetchProductListView.urlname),
    url(r'^products/new/$', NewProductView.as_view(), name=NewProductView.urlname),
    url(r'^products/(?P<prod_id>[\w-]+)/$', EditProductView.as_view(), name=EditProductView.urlname),
    url(r'^programs/$', ProgramListView.as_view(), name=ProgramListView.urlname),
    url(r'^programs/list/$', FetchProgramListView.as_view(), name=FetchProgramListView.urlname),
    url(r'^programs/new/$', NewProgramView.as_view(), name=NewProgramView.urlname),
    url(r'^programs/(?P<prog_id>[\w-]+)/$', EditProgramView.as_view(), name=EditProgramView.urlname),
    url(r'^programs/(?P<prog_id>[\w-]+)/productlist/$', FetchProductForProgramListView.as_view(),
        name=FetchProductForProgramListView.urlname),
    url(r'^default_consumption/$', DefaultConsumptionView.as_view(), name=DefaultConsumptionView.urlname),
)
