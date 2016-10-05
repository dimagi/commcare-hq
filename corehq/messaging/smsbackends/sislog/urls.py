from django.conf.urls import patterns, url

from corehq.messaging.smsbackends.sislog.views import sms_in

urlpatterns = patterns('corehq.messaging.smsbackends.sislog.views',
    url(r'^in/?$', sms_in, name='sms_in'),
)
