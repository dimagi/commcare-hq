from django.conf.urls import *

urlpatterns = patterns('commcarehq.messaging.smsbackends.telerivet.views',
    url(r'^in/?$', 'incoming_message', name='incoming_message'),
)
