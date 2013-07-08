from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.indicator_fixtures.views',
                       url(r'^$', 'view', name='mobile_indicators'),
                       )
