from django.conf.urls.defaults import *


urlpatterns = patterns('',
    url(r'^$', 'organization.views.org_report', name='org_report'),    
    (r'^charts/default/$', 'organization.views.summary_trend'),
    (r'^charts/$', 'organization.views.domain_charts'),
)
