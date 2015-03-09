from django.conf.urls import patterns, url
from custom.dhis2.views import check_repeaters

urlpatterns = patterns('custom.dhis2.views',
    url(r'^check/$', check_repeaters, name='check_repeaters'),
)
