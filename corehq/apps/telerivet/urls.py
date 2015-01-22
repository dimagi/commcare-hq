from django.conf.urls import *

urlpatterns = patterns('corehq.apps.telerivet.views',
    url(r'^in/?$', 'incoming_message', name='incoming_message'),
)
