from django.conf.urls.defaults import *

urlpatterns = patterns('custom.apps.wisepill.views',
    url(r'^device/?$', 'device_data', name='device_data'),
)
