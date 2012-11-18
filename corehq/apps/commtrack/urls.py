#from django.conf.urls.defaults import patterns, url
from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.commtrack.views',
    url(r'^debug/bootstrap/$', 'bootstrap'),
    url(r'^debug/import_locations/$', 'location_import'),
)
