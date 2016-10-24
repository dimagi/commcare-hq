from django.conf.urls import patterns, url
from corehq.apps.hqpillow_retry.views import EditPillowError

urlpatterns = patterns('corehq.apps.hqpillow_retry.views',
    url(r'^edit_errors/$', EditPillowError.as_view(), name=EditPillowError.urlname),

)
