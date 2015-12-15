from django.conf.urls import patterns, url
from corehq.apps.tour.views import EndTourView

urlpatterns = patterns('corehq.apps.tour.views',
    url(r'^end/(?P<tour_slug>\w+)/$', EndTourView.as_view(), name=EndTourView.urlname),
)
