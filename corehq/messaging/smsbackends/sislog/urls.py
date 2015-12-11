from django.conf.urls import *

urlpatterns = patterns('corehq.messaging.smsbackends.sislog.views',
    url(r'^in/?$', 'sms_in', name='sms_in'),
)
