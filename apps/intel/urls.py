from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^intel/?$', 'intel.views.default_report'),
    (r'^intel/all/?$', 'intel.views.default_report'),
)