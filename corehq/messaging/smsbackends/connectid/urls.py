from django.urls import re_path as url
from corehq.messaging.smsbackends.connectid.views import (
    connectid_messaging_key,
    receive_message,
    update_connectid_messaging_consent,
    messaging_callback_url
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
    url(r'^callback$', messaging_callback_url, name="connect_message_callback"),
]
