from django.conf.urls import re_path as url
from corehq.apps.events.views import (
    EventsView,
    EventCreateView,
    EventEditView,
    AttendeesListView,
    paginate_attendee_users,
)

urlpatterns = [
    url(r'^$', EventsView.as_view(), name=EventsView.urlname),
    url(r'^new/$', EventCreateView.as_view(), name=EventCreateView.urlname),
    url(r'^users/$', paginate_attendee_users, name='paginate_attendee_users'),
    url(r'^attendees/$', AttendeesListView.as_view(), name=AttendeesListView.urlname),
    url(r'^(?P<event_id>[\w-]+)/$', EventEditView.as_view(), name=EventEditView.urlname),
]
