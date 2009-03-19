from django.conf.urls.defaults import *


urlpatterns = patterns('',                       
    url(r'^submit/$', 'submitlogger.views.raw_submit', name='raw_submit'),
    url(r'^review/$', 'submitlogger.views.show_submits', name='show_submits'),
    url(r'^review/(?P<submit_id>\d)$', 'submitlogger.views.single_submission', name='single_submission'),
)
