from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url

from corehq.apps.mobile_auth.views import fetch_key_records, admin_fetch_key_records

urlpatterns = [
    url('^keys/$', fetch_key_records, name='key_server_url'),
    url('^admin_keys/$', admin_fetch_key_records, name='admin_key_server_url'),
]
