from django.conf.urls import *

urlpatterns = patterns('',         
    url(r'^in/$', 'commcarehq.messaging.smsbackends.unicel.views.incoming'),
)

