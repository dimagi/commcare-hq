from django.conf.urls import re_path as url

from .views import (
    AttendeeEditView,
    AttendeesConfigView,
    AttendeesListView,
    EventCreateView,
    EventEditView,
    EventsView,
    paginated_attendees,
    ConvertMobileWorkerAttendeesView,
    MobileWorkerAttendeeSatusView,
    poll_mobile_worker_attendee_progress,
)

urlpatterns = [
    url(r'^list/$', EventsView.as_view(), name=EventsView.urlname),
    url(r'^new/$', EventCreateView.as_view(), name=EventCreateView.urlname),
    url(r'^attendees/$', AttendeesListView.as_view(),
        name=AttendeesListView.urlname),
    url(r'^attendees/json/$', paginated_attendees, name='paginated_attendees'),
    url(r'^attendees/config/$', AttendeesConfigView.as_view(),
        name=AttendeesConfigView.urlname),
    url(r'^attendees/convert_users/$',
        ConvertMobileWorkerAttendeesView.as_view(), name=ConvertMobileWorkerAttendeesView.urlname),
    url(r'^attendees/(?P<attendee_id>[\w-]+)$', AttendeeEditView.as_view(),
        name=AttendeeEditView.urlname),
    url(r'^(?P<event_id>[\w-]+)/$', EventEditView.as_view(),
        name=EventEditView.urlname),
    url(r'^attendees/convert_users/status/(?P<download_id>(?:dl-)?[0-9a-fA-Z]{25,32})/$',
        MobileWorkerAttendeeSatusView.as_view(), name=MobileWorkerAttendeeSatusView.urlname),
    url(r'^attendees/convert_users/status/poll/(?P<download_id>(?:dl-)?[0-9a-fA-Z]{25,32})/$',
        poll_mobile_worker_attendee_progress,
        name='poll_mobile_worker_attendee_progress'),
]
