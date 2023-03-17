from django.conf.urls import re_path as url

from .views import (
    AttendeesListView,
    EventCreateView,
    EventEditView,
    EventsView,
    AttendeesConfigView,
    paginated_attendees,
)

urlpatterns = [
    url(r'^list/$', EventsView.as_view(), name=EventsView.urlname),
    url(r'^new/$', EventCreateView.as_view(), name=EventCreateView.urlname),
    url(r'^attendees/json/$', paginated_attendees, name='paginated_attendees'),
    url(r'^attendees/$', AttendeesListView.as_view(), name=AttendeesListView.urlname),
    url(r'^attendees/config$', AttendeesConfigView.as_view(), name=AttendeesConfigView.urlname),
    url(r'^(?P<event_id>[\w-]+)/$', EventEditView.as_view(), name=EventEditView.urlname),
]
