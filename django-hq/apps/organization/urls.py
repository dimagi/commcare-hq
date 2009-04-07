from django.conf.urls.defaults import *


urlpatterns = patterns('',
    url(r'^$', 'organization.views.reports', name='org_manager'),    
    (r'^charts/$', 'organization.views.summary_trend'),
)
