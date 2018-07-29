from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url

from corehq.messaging.smsbackends.tropo.views import ivr_in, sms_in

urlpatterns = [
    url(r'^sms/?$', sms_in, name='sms_in'),
    url(r'^ivr/?$', ivr_in, name='ivr_in'),
]
