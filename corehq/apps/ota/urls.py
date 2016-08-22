from django.conf.urls import url, patterns
from corehq.apps.ota.views import PrimeRestoreCacheView, AdvancedPrimeRestoreCacheView
from corehq.apps.hqadmin.views import DomainAdminRestoreView


urlpatterns = patterns('corehq.apps.ota.views',
    url(r'^restore/$', 'restore', name='ota_restore'),
    url(r'^admin_restore/$', DomainAdminRestoreView.as_view(), name=DomainAdminRestoreView.urlname),
    url(r'^restore/(?P<app_id>[\w-]+)/$', 'restore', name='app_aware_restore'),
    url(r'^prime_restore/$', PrimeRestoreCacheView.as_view(), name=PrimeRestoreCacheView.urlname),
    url(r'^prime_restore/advanced/$', AdvancedPrimeRestoreCacheView.as_view(),
        name=AdvancedPrimeRestoreCacheView.urlname),
    url(r'^search/$', 'search', name='remote_search'),
    url(r'^claim-case/$', 'claim', name='claim_case'),
)
