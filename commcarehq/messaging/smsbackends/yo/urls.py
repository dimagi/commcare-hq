from django.conf.urls import *

urlpatterns = patterns('commcarehq.messaging.smsbackends.yo.views',
    url(r'^sms/?$', 'sms_in', name='sms_in'),
)
