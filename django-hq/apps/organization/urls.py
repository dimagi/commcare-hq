from django.conf.urls.defaults import *


urlpatterns = patterns('',
    url(r'^$', 'organization.views.org_report', name='org_report'),    
    (r'^charts/$', 'organization.views.domain_charts'),
)
