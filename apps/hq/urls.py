from django.conf.urls.defaults import *
import hq.views as views

urlpatterns = patterns('',
    (r'^$', 'hq.views.dashboard'),    
    (r'^serverup.txt$', 'hq.views.server_up'),
    (r'^change_password/?$', 'hq.views.password_change'),
    
    url(r'^report/?$', 'hq.views.org_report', name='org_report'),    
    (r'^no_permissions/?$', 'hq.views.no_permissions'),
    
    (r'^report/email/?$', 'hq.views.org_email_report'),    
    (r'^report/sms/?$', 'hq.views.org_sms_report'),    
    
    url(r'^reporters/add/?$',         views.add_reporter,  name="add-reporter"),
    url(r'^reporters/(?P<pk>\d+)/?$', views.edit_reporter, name="view-reporter"),
       
    (r'^stats/?$', 'hq.views.reporter_stats'),
    (r'^stats/delinquents?/?$', 'hq.views.delinquent_report'),
    
    (r'', include('hq.reporter.api_.urls')),    
)
