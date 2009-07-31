from django.conf.urls.defaults import *


urlpatterns = patterns('',                       
    url(r'^receiver/submit/$', 'receiver.views.raw_submit', name='raw_submit'),
    url(r'^receiver/submit/(?P<domain_name>.*)$', 'receiver.views.domain_submit', name='domain_submit'),
    url(r'^receiver/resubmit/(?P<domain_name>.*)$', 'receiver.views.domain_resubmit', name='domain_resubmit'),
    url(r'^receiver/submitraw/?', 'receiver.views.save_post'),
    url(r'^receiver/backup/(?P<domain_name>.*)$', 'receiver.views.backup', name='backup'),
    url(r'^receiver/restore/(?P<code_id>\d+)$', 'receiver.views.restore', name='restore'),
    url(r'^receiver/review$', 'receiver.views.show_submits', name='show_submits'),
    url(r'^receiver/review/(?P<submission_id>\d+)$', 'receiver.views.single_submission', name='single_submission'),
    url(r'^receiver/attachment/(?P<attachment_id>\d+)$', 'receiver.views.single_attachment', name='single_attachment'),
    url(r'^receiver/orphaned_data/$', 'receiver.views.orphaned_data', name='orphaned_data'),
)
