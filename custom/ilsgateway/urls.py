from django.conf.urls import patterns, url
from custom.ilsgateway.views import GlobalStats


urlpatterns = patterns('custom.ilsgateway.views',
    url(r'^global_stats/$', GlobalStats.as_view(), name=GlobalStats.urlname)
)