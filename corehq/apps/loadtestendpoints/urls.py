from django.conf.urls import url

from corehq.apps.loadtestendpoints.views import noop, saving

urlpatterns = [
    url(r'^noop/$', noop, name='noop'),
    url(r'^saving/$', saving, name='saving'),
]
