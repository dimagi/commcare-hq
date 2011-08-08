from django.conf.urls.defaults import *

urlpatterns = patterns('reports.pathfinder.views',
    url('hbc/(?P<ward>.*)/(?P<year>\d*)/(?P<month>\d*)', 'home_based_care'),
    url('ward/(?P<ward>.*)/(?P<year>\d*)/(?P<month>\d*)', 'ward_summary'),
    url('provider/(?P<name>.*)/(?P<year>\d*)/(?P<month>\d*)', 'provider_summary'),
)

