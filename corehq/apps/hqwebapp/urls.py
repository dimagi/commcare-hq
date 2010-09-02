from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns('',
    url(r'^$',       'corehq.apps.hqwebapp.views.dashboard', name="homepage"),    
    (r'^serverup.txt$', 'corehq.apps.hqwebapp.views.server_up'),
    (r'^change_password/?$', 'corehq.apps.hqwebapp.views.password_change'),
    
    (r'^no_permissions/?$', 'corehq.apps.hqwebapp.views.no_permissions'),
    
    url(r'^accounts/login/$', 'corehq.apps.hqwebapp.views.login', name="login"),
    url(r'^accounts/logout/$', 'corehq.apps.hqwebapp.views.logout', name="logout"),
)

