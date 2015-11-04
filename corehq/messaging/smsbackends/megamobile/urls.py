from django.conf.urls import *

urlpatterns = patterns('corehq.messaging.smsbackends.megamobile.views',
    url(r'^sms/?$', 'sms_in', name='sms_in'),
)
