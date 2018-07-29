from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.messaging.smsbackends.telerivet.views import TelerivetSetupView, incoming_message
from django.conf.urls import url


urlpatterns = [
    url(r'^in/?$', incoming_message, name='telerivet_in'),
]


domain_specific = [
    url(r'^setup/$', TelerivetSetupView.as_view(), name=TelerivetSetupView.urlname),
]
