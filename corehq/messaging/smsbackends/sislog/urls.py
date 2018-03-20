from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url

from corehq.messaging.smsbackends.sislog.views import sms_in

urlpatterns = [
    url(r'^in/?$', sms_in, name='sms_in'),
]
