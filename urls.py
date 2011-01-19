from django.conf.urls.defaults import *

urlpatterns = patterns('',                       
    url(r'^test/$', 'corehq.apps.phone.views.test'),
    url(r'^restore/$', 'corehq.apps.phone.views.restore'),
    url(r'^logs/$', 'corehq.apps.phone.views.logs', name="phone_sync_logs"),
    url(r'^logs/single/(?P<chw_id>\w+)/$', 'corehq.apps.phone.views.logs_for_chw', name="phone_sync_logs_for_chw"),
)

