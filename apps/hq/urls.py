from django.conf.urls.defaults import *


urlpatterns = patterns('',
    (r'^$', 'hq.views.dashboard'),    
    (r'^change_password/?$', 'hq.views.password_change'),
    
    url(r'^report/?$', 'hq.views.org_report', name='org_report'),    
    
    (r'^report/email/?$', 'hq.views.org_email_report'),    
    (r'^report/sms/?$', 'hq.views.org_sms_report'),    
    
    
    
    (r'^charts/default/?$', 'hq.views.summary_trend'),
    (r'^charts/?$', 'hq.views.domain_charts'),    
    (r'^stats/?$', 'hq.views.reporter_stats'),
    (r'^stats/delinquents?$', 'hq.views.delinquent_report'),
    (r'', include('hq.reporter.api_.urls')),    
)
