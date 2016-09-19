from django.conf.urls import patterns, url

from corehq.messaging.smsbackends.megamobile.views import sms_in

urlpatterns = patterns('corehq.messaging.smsbackends.megamobile.views',
    url(r'^sms/?$', sms_in, name='sms_in'),
)
