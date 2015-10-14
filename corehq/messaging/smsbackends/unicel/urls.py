from django.conf.urls import *

urlpatterns = patterns('',         
    url(r'^in/$', 'corehq.messaging.smsbackends.unicel.views.incoming'),
)

