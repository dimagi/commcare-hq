from django.conf.urls import *

urlpatterns = patterns('corehq.messaging.smsbackends.telerivet.views',
    url(r'^in/?$', 'incoming_message', name='incoming_message'),
)
