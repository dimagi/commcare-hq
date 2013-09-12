#from django.conf.urls.defaults import patterns, url
from django.conf.urls.defaults import *
from corehq.apps.commtrack.views import ProductListView, FetchProductListView, NewProductView, EditProductView

urlpatterns = patterns('corehq.apps.commtrack.views',
    url(r'^debug/bootstrap/$', 'bootstrap'),
    url(r'^debug/import_locations/$', 'location_import'),
    url(r'^debug/import_history/$', 'historical_import'),
    url(r'^debug/charts/$', 'charts'),
    url(r'^debug/location_dump/$', 'location_dump'),

    url(r'^api/supply_point_query/$', 'api_query_supply_point'),
)

# used in settings urls
settings_urls = patterns('corehq.apps.commtrack.views',
    url(r'^products/$', ProductListView.as_view(), name=ProductListView.urlname),
    url(r'^products/list/$', FetchProductListView.as_view(), name=FetchProductListView.urlname),
    url(r'^products/new/$', NewProductView.as_view(), name=NewProductView.urlname),
    url(r'^products/(?P<prod_id>[\w-]+)/$', EditProductView.as_view(), name=EditProductView.urlname),
)
