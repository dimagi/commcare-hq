from django.conf.urls.defaults import *


urlpatterns = patterns('',                       
    url(r'^submit/$', 'receiver.views.raw_submit', name='raw_submit'),
    url(r'^backup/$', 'receiver.views.backup', name='backup'),
    url(r'^review/$', 'receiver.views.show_submits', name='show_submits'),
    url(r'^review/(?P<submission_id>\d+)$', 'receiver.views.single_submission', name='single_submission'),
)
