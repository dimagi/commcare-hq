from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.cleanup.views',
    # stub urls
    #(r'', 'links'),
    (r'^submissions.json$', 'submissions_json'),
    (r'^users\.json$', 'users_json'),
    (r'^submissions/$', 'submissions'),
    (r'^relabel_submissions/$', 'relabel_submissions'),


    (r'^cases\.json$', 'cases_json'),
    (r'^cases/$', 'cases'),
    (r'^close_cases/$', 'close_cases'),

    url(r'^change_submissions_app_id/$', 'change_submissions_app_id', name="change_submissions_app_id"),
    url(r'^delete_all_data/$', 'delete_all_data', name="cleanup_delete_all_data"),
)