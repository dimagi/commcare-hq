from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.appstore.views',
    url(r'^$', 'appstore', name='appstore'),
    url(r'^(?P<domain>[\w\.-]+)/$', 'app_info', name='app_info')
)