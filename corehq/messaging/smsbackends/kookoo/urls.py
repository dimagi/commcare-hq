from django.conf.urls import *

urlpatterns = patterns('corehq.messaging.smsbackends.kookoo.views',
    url(r'^ivr/?$', 'ivr', name='ivr'),
    url(r'^ivr_finished/?$', 'ivr_finished', name='ivr_finished'),
)
