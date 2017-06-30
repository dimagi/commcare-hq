from django.conf.urls import url

from corehq.messaging.scheduling.views import BroadcastListView

urlpatterns = [
    url(r'^broadcasts/$', BroadcastListView.as_view(), name=BroadcastListView.urlname),
]
