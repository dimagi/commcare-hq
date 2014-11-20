from django.conf.urls import url, patterns

urlpatterns = patterns('',
    url(r'^restore/$', 'corehq.apps.ota.views.restore'),
    url(r'^prime_restore/$', 'corehq.apps.ota.views.prime_ota_restore_cache'),
)
