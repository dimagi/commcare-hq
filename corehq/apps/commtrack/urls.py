#from django.conf.urls.defaults import patterns, url
from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.commtrack.views',
    url(r'^debug/bootstrap/$', 'bootstrap'),
    url(r'^debug/import_locations/$', 'location_import'),
    url(r'^debug/import_history/$', 'historical_import'),
)

# used in settings urls
settings_urls = patterns('corehq.apps.commtrack.views',
    url(r'^products/$', 'product_list', name='commtrack_product_list'),
    url(r'^products/list/$', 'product_fetch', name='commtrack_product_fetch'),
    url(r'^products/(?P<prod_id>[\w-]+)/$', 'product_edit', name='commtrack_product_edit'),
    url(r'^products/new/$', 'product_edit', name='commtrack_product_new'),
)
