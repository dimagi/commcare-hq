from django.conf.urls import url
from corehq.apps.hqpillow_retry.views import EditPillowError

urlpatterns = [
    url(r'^edit_errors/$', EditPillowError.as_view(), name=EditPillowError.urlname),
]
