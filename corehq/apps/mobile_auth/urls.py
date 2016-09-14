from django.conf.urls import url, patterns

from corehq.apps.mobile_auth.views import fetch_key_records, admin_fetch_key_records

urlpatterns = patterns('corehq.apps.mobile_auth.views',
    url('^keys/$', fetch_key_records, name='key_server_url'),
    url('^admin_keys/$', admin_fetch_key_records, name='admin_key_server_url'),
)
