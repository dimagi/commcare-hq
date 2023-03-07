from django.conf.urls import re_path as url

from .views import EventCreateView, EventsView

urlpatterns = [
    url(r'^$', EventsView.as_view(), name=EventsView.urlname),
    url(r'^new/$', EventCreateView.as_view(), name=EventCreateView.urlname),
]
