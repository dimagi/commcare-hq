from django.conf.urls import re_path as url
from corehq.apps.events.views import (
    EventsView,
    EventCreateView,
    EventEditView,
    AttendeesAddView,
    paginate_possible_attendees,
)

urlpatterns = [
    url(r'^$', EventsView.as_view(), name=EventsView.urlname),
    url(r'^new/$', EventCreateView.as_view(), name=EventCreateView.urlname),
    url(r'^(?P<event_id>[\w-]+)/$', EventEditView.as_view(), name=EventEditView.urlname),
    url(r'^attendees/$', AttendeesAddView.as_view(), name=AttendeesAddView.urlname),
    url(r'^users/$', paginate_possible_attendees, name='paginate_possible_attendees'),
]
