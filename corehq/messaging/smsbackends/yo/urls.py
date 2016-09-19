from django.conf.urls import patterns, url

from corehq.messaging.smsbackends.yo.views import sms_in

urlpatterns = patterns('corehq.messaging.smsbackends.yo.views',
    url(r'^sms/?$', sms_in, name='sms_in'),
)
