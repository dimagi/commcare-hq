from django.conf.urls import url

from corehq.apps.hqcouchlog.views import fail

urlpatterns = [
    url(r'^fail/$', fail, name='fail'),
]
