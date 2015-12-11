from django.conf.urls import url, patterns
from corehq.apps.ota.views import PrimeRestoreCacheView


urlpatterns = patterns('corehq.apps.ota.views',
    url(r'^restore/$', 'restore'),
    url(r'^prime_restore/$', PrimeRestoreCacheView.as_view(), name=PrimeRestoreCacheView.urlname),
)
