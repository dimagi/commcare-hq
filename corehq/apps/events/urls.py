from django.conf.urls import re_path as url
from corehq.apps.events.views import EventsCRUDView

urlpatterns = [
    url(r'^$', EventsCRUDView.as_view(), name=EventsCRUDView.urlname),
]
