from __future__ import absolute_import
from django.conf.urls import url

from corehq.messaging.smsbackends.unicel.views import incoming

urlpatterns = [
    url(r'^in/$', incoming, name='incoming'),
]
