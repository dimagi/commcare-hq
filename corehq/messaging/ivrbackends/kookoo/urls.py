from __future__ import absolute_import
from django.conf.urls import url

from corehq.messaging.ivrbackends.kookoo.views import ivr, ivr_finished

urlpatterns = [
    url(r'^ivr/?$', ivr, name='ivr'),
    url(r'^ivr_finished/?$', ivr_finished, name='ivr_finished'),
]
