from django.conf.urls import url, patterns
from corehq.apps.ota.views import PrimeRestoreCacheView, AdvancedPrimeRestoreCacheView


urlpatterns = patterns('corehq.apps.ota.views',
    url(r'^restore/$', 'restore', name='ota_restore'),
    url(r'^restore/(?P<app_id>[\w-]+)/$', 'restore', name='app_aware_restore'),
    url(r'^prime_restore/$', PrimeRestoreCacheView.as_view(), name=PrimeRestoreCacheView.urlname),
    url(r'^prime_restore/advanced/$', AdvancedPrimeRestoreCacheView.as_view(),
        name=AdvancedPrimeRestoreCacheView.urlname),
)
