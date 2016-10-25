from corehq.messaging.smsbackends.telerivet.views import TelerivetSetupView, incoming_message
from django.conf.urls import patterns, url


urlpatterns = patterns('corehq.messaging.smsbackends.telerivet.views',
    url(r'^in/?$', incoming_message, name='telerivet_in'),
)


domain_specific = patterns('corehq.messaging.smsbackends.telerivet.views',
    url(r'^setup/$', TelerivetSetupView.as_view(), name=TelerivetSetupView.urlname),
)
