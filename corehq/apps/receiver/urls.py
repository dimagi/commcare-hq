from django.conf.urls.defaults import *


urlpatterns = patterns('',                       
    
    # ODK API
    url(r'^receiver/submit/(?P<domain_name>.*)/formList/?$', 'corehq.apps.receiver.views.form_list', name='form_list'),

    url(r'^receiver/submit/$', 'corehq.apps.receiver.views.raw_submit', name='raw_submit'),
    url(r'^receiver/submit/(?P<domain_name>.*)$', 'corehq.apps.receiver.views.domain_submit', name='domain_submit'),
    url(r'^receiver/resubmit/(?P<domain_name>.*)$', 'corehq.apps.receiver.views.domain_resubmit', name='domain_resubmit'),
    url(r'^receiver/review/?$', 'corehq.apps.receiver.views.show_submits', name='show_submits'),
    url(r'^receiver/review/dupes/(?P<submission_id>\d+)/?$', 'corehq.apps.receiver.views.show_dupes', name='show_dupes'),
    url(r'^receiver/review/(?P<submission_id>\d+)/delete/?$', 'corehq.apps.receiver.views.delete_submission', name='delete_submission'),
    url(r'^receiver/review/(?P<submission_id>\d+)/?$', 'corehq.apps.receiver.views.single_submission', name='single_submission'),
    url(r'^receiver/attachment/(?P<attachment_id>\d+)/?$', 'corehq.apps.receiver.views.single_attachment', name='single_attachment'),
    url(r'^receiver/annotations/new/?$', 'corehq.apps.receiver.views.new_annotation', name='new_annotation'),
    url(r'^receiver/annotations/(?P<attachment_id>\d+)/?$', 'corehq.apps.receiver.views.annotations', name='annotations'),
    url(r'^receiver/orphaned_data/$', 'corehq.apps.receiver.views.orphaned_data', name='orphaned_data'),
    url(r'^receiver/orphaned_data/xml/?$', 'corehq.apps.receiver.views.orphaned_data_xml', name='orphaned_data_xml'),
    (r'', include('corehq.apps.receiver.api_.urls')),
)
