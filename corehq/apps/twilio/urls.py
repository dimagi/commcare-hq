from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.twilio.views',
    url(r'^sms/?$', 'sms_in', name='twilio_sms_in'),
)
