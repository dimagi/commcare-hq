from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.hqwebapp.views',
    url(r'^homepage/$', 'redirect_to_default', name='homepage'),
    url(r'^home/$', 'landing_page', name='landing_page'),
    url(r'^crossdomain.xml$', 'yui_crossdomain', name='yui_crossdomain'),
    (r'^serverup.txt$', 'server_up'),
    (r'^change_password/$', 'password_change'),
    
    url(r'^no_permissions/$', 'no_permissions', name='no_permissions'),
    
    url(r'^accounts/login/$', 'login', name="login"),
    url(r'^accounts/logout/$', 'logout', name="logout"),
    (r'^$', 'redirect_to_default'),
    (r'^reports/$', 'redirect_to_default'),
    url(r'^bug_report/$', 'bug_report', name='bug_report'),
    url(r'^debug/notify/$', 'debug_notify', name='debug_notify'),
)

urlpatterns += patterns('corehq.apps.orgs.views', url(r'^search_orgs/', 'search_orgs', name='search_orgs'))

domain_specific = patterns('corehq.apps.hqwebapp.views',
    url(r'^$', 'redirect_to_default', name='domain_homepage'),
    url(r'^login/$', 'domain_login', name='domain_login'),
    url(r'^login/mobile/$', 'domain_login', name='domain_mobile_login', 
        kwargs={'template_name': 'login_and_password/mobile_login.html'}),
    url(r'^retreive_download/(?P<download_id>[0-9a-fA-Z]{25,32})/$', 
        'retrieve_download', {'template': 'hqwebapp/file_download.html' },
        name='hq_soil_download')
)
