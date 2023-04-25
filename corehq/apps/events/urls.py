from django.conf.urls import re_path as url

from .views import (
    AttendeeEditView,
    AttendeeDeleteView,
    AttendeesConfigView,
    AttendeesListView,
    EventCreateView,
    EventEditView,
    EventsView,
    paginated_attendees,
)

urlpatterns = [
    url(r'^list/$', EventsView.as_view(), name=EventsView.urlname),
    url(r'^new/$', EventCreateView.as_view(), name=EventCreateView.urlname),
    url(r'^attendees/$', AttendeesListView.as_view(),
        name=AttendeesListView.urlname),
    url(r'^attendees/json/$', paginated_attendees, name='paginated_attendees'),
    url(r'^attendees/config/$', AttendeesConfigView.as_view(),
        name=AttendeesConfigView.urlname),
    url(r'^attendees/(?P<attendee_id>[\w-]+)$', AttendeeEditView.as_view(),
        name=AttendeeEditView.urlname),
    url(r'^(?P<event_id>[\w-]+)/$', EventEditView.as_view(),
        name=EventEditView.urlname),
    url(r'^attendees/delete/(?P<attendee_id>[\w-]+)/$', AttendeeDeleteView.as_view(),
        name=AttendeeDeleteView.urlname),
]
