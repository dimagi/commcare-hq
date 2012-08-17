from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns('corehq.apps.hqwebapp.views',
    url(r'^homepage/$', 'redirect_to_default', name='homepage'),
    url(r'^home/$', 'landing_page', name='landing_page'),
    url(r'^crossdomain.xml$', 'yui_crossdomain', name='yui_crossdomain'),
    (r'^serverup.txt$', 'server_up'),
    (r'^change_password/$', 'password_change'),
    
    (r'^no_permissions/$', 'no_permissions'),
    
    url(r'^accounts/login/$', 'login', name="login"),
    url(r'^accounts/logout/$', 'logout', name="logout"),
    (r'^$', 'redirect_to_default'),
    (r'^reports/$', 'redirect_to_default'),
    url(r'^bug_report/$', 'bug_report', name='bug_report'),
    url(r'^debug/notify/$', 'debug_notify', name='debug_notify'),
)

domain_specific = patterns('corehq.apps.hqwebapp.views',
 url(r'^$', 'redirect_to_default', name='domain_homepage'),
)