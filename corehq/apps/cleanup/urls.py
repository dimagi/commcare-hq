from django.conf.urls import *

urlpatterns = patterns('corehq.apps.cleanup.views',

    url(r'^change_submissions_app_id/$', 'change_submissions_app_id', name="change_submissions_app_id"),
)
