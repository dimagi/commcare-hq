from django.conf.urls import *

urlpatterns = patterns('pathfinder.views',
    url(r'select/$', 'selector'),
    url('select/ward', 'ward_selector'),
    url('select/provider', 'provider_selector'),
    url('select/hbc', 'hbc_selector'),
    url('hbc/', 'home_based_care'),
    url('ward/', 'ward_summary'),
    url('provider/', 'provider_summary'),
)

