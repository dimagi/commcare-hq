from corehq.messaging.smsbackends.telerivet.views import TelerivetSetupView, incoming_message
from django.conf.urls import url
from .views import create_backend, get_last_inbound_sms, send_sample_sms


urlpatterns = [
    url(r'^in/?$', incoming_message, name='telerivet_in'),
]


domain_specific = [
    url(r'^setup/$', TelerivetSetupView.as_view(), name=TelerivetSetupView.urlname),
    url(r'^setup/get_last_inbound_sms/$', get_last_inbound_sms, name='get_last_inbound_sms'),
    url(r'^setup/send_sample_sms/$', send_sample_sms, name='send_sample_sms'),
    url(r'^setup/create_backend/$', create_backend, name='create_backend'),
]
