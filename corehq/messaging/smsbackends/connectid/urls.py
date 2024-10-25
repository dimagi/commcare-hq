from django.urls import re_path as url
from corehq.messaging.smsbackends.connectid.views import (
    connectid_messaging_key,
    receive_message,
    update_connectid_messaging_consent
)

urlpatterns = [
    url(r'^message$', receive_message, name="receive_connect_message"),
    url(
        r'^messaging_key/$',
        connectid_messaging_key,
        name='connectid_messaging_key',
    ),
    url(
        r'^update_messaging_consent/$',
        update_connectid_messaging_consent,
        name='update_connectid_messaging_consent',
    ),
]
