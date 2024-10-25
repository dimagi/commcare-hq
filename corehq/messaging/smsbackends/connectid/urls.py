from django.urls import re_path as url
from corehq.messaging.smsbackends.connectid.views import receive_message


urlpatterns = [
    url(r'^message$', receive_message, name="receive_connect_message"),
]
