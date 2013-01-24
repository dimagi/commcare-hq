#from django.conf.urls.defaults import patterns, url
from django.conf.urls.defaults import *

#urlpatterns = patterns('corehq.apps.locations.views',
#)

# used in settings urls
settings_urls = patterns('corehq.apps.locations.views',
    url(r'^$', 'locations_list', name='manage_locations'),
    url(r'^new/$', 'location_edit', name='create_location'),
    url(r'^(?P<loc_id>[\w-]+)/$', 'location_edit', name='edit_location'),
)
