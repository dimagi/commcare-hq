from django.conf.urls import *
from corehq.apps.pillow_retry.views import EditPillowError

urlpatterns = patterns('corehq.apps.pillow_retry.views',
    url(r'^edit_errors/$', EditPillowError.as_view(), name=EditPillowError.urlname),

)
