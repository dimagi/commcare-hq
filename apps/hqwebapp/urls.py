from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns('',
    url(r'^$',       'hqwebapp.views.dashboard', name="homepage"),    
    (r'^serverup.txt$', 'hqwebapp.views.server_up'),
    (r'^change_password/?$', 'hqwebapp.views.password_change'),
    
    (r'^no_permissions/?$', 'hqwebapp.views.no_permissions'),
    
    url(r'^accounts/login/$', 'hqwebapp.views.login', name="login"),
    url(r'^accounts/logout/$', 'hqwebapp.views.logout', name="logout"),
)

