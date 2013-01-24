#from django.conf.urls.defaults import patterns, url
from django.conf.urls.defaults import *

#urlpatterns = patterns('corehq.apps.locations.views',
#)

# used in settings urls
settings_urls = patterns('corehq.apps.locations.views',
    url(r'^$', 'locations_list', name='manage_locations'),
#    url(r'^products/list/$', 'product_fetch', name='commtrack_product_fetch'),
#    url(r'^products/new/$', 'product_edit', name='commtrack_product_new'),
#    url(r'^products/(?P<prod_id>[\w-]+)/$', 'product_edit', name='commtrack_product_edit'),
)
