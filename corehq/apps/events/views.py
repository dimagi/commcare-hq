from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.http import HttpResponseRedirect, HttpResponseBadRequest
from django.http import Http404

from corehq.apps.hqwebapp.views import CRUDPaginatedViewMixin
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.events.models import (
    Event,
    get_domain_events,
)
from corehq.apps.events.forms import CreateEventForm
from corehq.apps.hqwebapp.decorators import use_jquery_ui
from corehq import toggles


class BaseEventView(BaseDomainView):
    urlname = "events_page"
    section_name = _("Attendance Tracking")

    def dispatch(self, *args, **kwargs):
        # The FF check is temporary till the full feature is released
        toggle_enabled = toggles.ATTENDANCE_TRACKING.enabled(self.domain)
        if not (self.request.couch_user.can_manage_events(self.domain) and toggle_enabled):
            raise Http404
        return super(BaseEventView, self).dispatch(*args, **kwargs)

    @property
    def section_url(self):
        return reverse(BaseEventView.urlname, args=(self.domain,))


class EventsView(BaseEventView, CRUDPaginatedViewMixin):
    urlname = "events_page"
    template_name = 'events_list.html'

    page_title = _("Attendance Tracking Events")

    limit_text = _("events per page")
    empty_notification = _("You have no events")
    loading_message = _("Loading events")

    @property
    def page_name(self):
        return _("Events")

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.domain,))

    @property
    def total(self):
        return len(self.domain_events)

    @property
    def column_names(self):
        return [
            _("Name"),
            _("Start date"),
            _("End date"),
            _("Attendance Target"),
            _("Total attendees"),
            _("Status"),
        ]

    @property
    def page_context(self):
        return self.pagination_context

    @property
    def domain_events(self):
        return get_domain_events(self.domain)

    @property
    def paginated_list(self):
        start, end = self.skip, self.skip + self.limit
        for event in self.domain_events[start:end]:
            yield {
                'itemData': self._format_paginated_event(event),
                'template': 'base-event-template'
            }

    def post(self, *args, **kwargs):
        return self.paginate_crud_response

    def _format_paginated_event(self, event: Event):
        return {
            'id': event.event_id,
            'name': event.name,
            'start_date': str(event.start_date),
            'end_date': str(event.end_date),
            'target_attendance': event.attendance_target,
            'total_attendance': event.total_attendance,
            'status': event.status,
        }


class EventCreateView(BaseEventView):
    urlname = 'add_attendance_tracking_event'
    template_name = "new_event.html"

    page_title = _("Add Attendance Tracking Event")

    @use_jquery_ui
    def dispatch(self, request, *args, **kwargs):
        return super(EventCreateView, self).dispatch(request, *args, **kwargs)

    @property
    def page_name(self):
        return _("Add new event")

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.domain,))

    @property
    def parent_pages(self):
        return [
            {
                'title': EventsView.page_title,
                'url': reverse(EventsView.urlname, args=[self.domain])
            },
        ]

    def get_context_data(self, **kwargs):
        context = super(EventCreateView, self).get_context_data(**kwargs)
        context.update({'form': self.form})
        return context

    def post(self, *args, **kwargs):
        form = self.form

        if not form.is_valid():
            return HttpResponseBadRequest()

        event_data = form.cleaned_data
        event_data['domain'] = self.domain
        event_data['manager'] = self.request.couch_user

        event = Event.get_obj_from_data(event_data)
        event.save()

        return HttpResponseRedirect(reverse(EventsView.urlname, args=(self.domain,)))

    @property
    def form(self):
        if self.request.method == 'POST':
            return CreateEventForm(self.request.POST)
        else:
            return CreateEventForm(initial={})
