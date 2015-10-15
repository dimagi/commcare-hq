from django.conf.urls import *

urlpatterns = patterns('corehq.apps.analytics.views',
    (r'^hubspot/click-deploy/$', 'hubspot_click_deploy'),
)