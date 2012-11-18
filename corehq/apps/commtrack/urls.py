#from django.conf.urls.defaults import patterns, url
from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.commtrack.views',
    url(r'^bootstrap/$', 'bootstrap'),
)
