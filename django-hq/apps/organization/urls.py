from django.conf.urls.defaults import *


urlpatterns = patterns('',
    #url(r'^report/?$', 'organization.views.org_report', name='org_report'),    
    (r'^$', 'organization.views.dashboard'),    
    url(r'^report/?$', 'organization.views.org_report', name='org_report'),
    (r'^report/email/?$', 'organization.views.org_email_report'),
    #(r'^report/email/(?P<id>\d*)/?$', 'organization.views.org_email_report'),
    (r'^report/sms/?$', 'organization.views.org_sms_report'),
    #(r'^report/sms/(?P<id>\d*)/?$', 'organization.views.org_sms_report'),
    (r'^charts/default/?$', 'organization.views.summary_trend'),
    (r'^charts/?$', 'organization.views.domain_charts'),
    
)
