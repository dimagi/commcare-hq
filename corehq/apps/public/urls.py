from django.conf.urls import patterns, url
from corehq.apps.public.views import *

urlpatterns = patterns(
    'corehq.apps.public.views',
    url(r'^$', 'public_default', name='public_default'),
    url(r'^home/$', HomePublicView.as_view(), name=HomePublicView.urlname),
    url(r'^impact/$', ImpactPublicView.as_view(), name=ImpactPublicView.urlname),
    url(r'^services/$', ServicesPublicView.as_view(),
        name=ServicesPublicView.urlname),
    url(r'^pricing/$', PricingPublicView.as_view(),
        name=PricingPublicView.urlname),
)
