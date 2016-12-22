from django.conf.urls import url

from corehq.messaging.smsbackends.megamobile.views import sms_in

urlpatterns = [
    url(r'^sms/?$', sms_in, name='sms_in'),
]
