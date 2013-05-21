from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.telerivet.views',
    url(r'^in/?$', 'incoming_message', name='incoming_message'),
)
