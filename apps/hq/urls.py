from django.conf.urls.defaults import *
import hq.views as views
import settings

urlpatterns = patterns('',
    url(r'^$', 'hq.views.dashboard', name="homepage"),    
    (r'^serverup.txt$', 'hq.views.server_up'),
    (r'^change_password/?$', 'hq.views.password_change'),
    
    (r'^no_permissions/?$', 'hq.views.no_permissions'),
    
    url(r'^reporters/add/?$',         views.add_reporter,  name="add-reporter"),
    url(r'^reporters/(?P<pk>\d+)/?$', views.edit_reporter, name="view-reporter"),
       
    (r'^stats/?$', 'hq.views.reporter_stats'),
    
    (r'', include('hq.reporter.api_.urls')),    
)

