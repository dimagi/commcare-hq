from django.conf.urls.defaults import *


urlpatterns = patterns('',
    url(r'^$', 'organization.views.manager', name='org_manager'),    
)
