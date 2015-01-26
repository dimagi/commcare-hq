from django.conf.urls import *

urlpatterns = patterns('corehq.apps.cleanup.views',

    url(r'^change_submissions_app_id/$', 'change_submissions_app_id', name="change_submissions_app_id"),
    url(r'^delete_all_data/$', 'delete_all_data'),

    # bihar migration
    url(r'reassign_cases_to_correct_owner/', 'reassign_cases_to_correct_owner', name='reassign_cases_to_correct_owner'),
)