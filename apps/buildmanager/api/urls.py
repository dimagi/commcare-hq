from django.conf.urls.defaults import *
from buildmanager.api.resources import *

urlpatterns = patterns('',
   (r'^api/builds/$', get_builds),
   (r'^api/(?P<domain_id>\d+)/builds/$', get_builds_for_domain),    
)

