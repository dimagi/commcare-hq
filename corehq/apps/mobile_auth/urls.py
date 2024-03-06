from django.urls import re_path as url

from corehq.apps.mobile_auth.views import (
    admin_fetch_key_records,
    fetch_key_records,
)

urlpatterns = [
    url('^keys/$', fetch_key_records, name='key_server_url'),
    url('^admin_keys/$', admin_fetch_key_records, name='admin_key_server_url'),
]
