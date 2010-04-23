from django.conf.urls.defaults import *


urlpatterns = patterns('',                       
    url(r'^receiver/submit/$', 'receiver.views.raw_submit', name='raw_submit'),
    url(r'^receiver/submit/(?P<domain_name>.*)$', 'receiver.views.domain_submit', name='domain_submit'),
    url(r'^receiver/resubmit/(?P<domain_name>.*)$', 'receiver.views.domain_resubmit', name='domain_resubmit'),
    url(r'^receiver/review/?$', 'receiver.views.show_submits', name='show_submits'),
    url(r'^receiver/review/dupes/(?P<submission_id>\d+)/?$', 'receiver.views.show_dupes', name='show_dupes'),
    url(r'^receiver/review/(?P<submission_id>\d+)/delete/?$', 'receiver.views.delete_submission', name='delete_submission'),
    url(r'^receiver/review/(?P<submission_id>\d+)/?$', 'receiver.views.single_submission', name='single_submission'),
    url(r'^receiver/attachment/(?P<attachment_id>\d+)/?$', 'receiver.views.single_attachment', name='single_attachment'),
    url(r'^receiver/annotations/new/?$', 'receiver.views.new_annotation', name='new_annotation'),
    url(r'^receiver/annotations/(?P<attachment_id>\d+)/?$', 'receiver.views.annotations', name='annotations'),
    url(r'^receiver/orphaned_data/$', 'receiver.views.orphaned_data', name='orphaned_data'),
    url(r'^receiver/orphaned_data/xml/?$', 'receiver.views.orphaned_data_xml', name='orphaned_data_xml'),
    (r'', include('receiver.api_.urls')),
)
