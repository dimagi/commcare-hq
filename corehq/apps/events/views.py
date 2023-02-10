from django.utils.translation import gettext_lazy
from django.urls import reverse

from corehq.apps.hqwebapp.views import CRUDPaginatedViewMixin
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.events.models import (
    Event,
    ATTENDEE_LIST_STATUS_CHOICES,
    domain_events_from_es,
    domain_events_es_query,
)


class EventsCRUDView(BaseDomainView, CRUDPaginatedViewMixin):
    urlname = "events_page"
    template_name = 'events_list.html'

    section_name = gettext_lazy("Events")
    page_title = gettext_lazy("Attendance Tracking Events")
    limit_text = gettext_lazy("events per page")
    empty_notification = gettext_lazy("You have no events")
    loading_message = gettext_lazy("Loading events")

    @property
    def section_url(self):
        return reverse(self.urlname, args=(self.domain,))

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.domain,))

    @property
    def total(self):
        return domain_events_es_query(self.domain).count()

    @property
    def column_names(self):
        return [
            "Name",
            "Start date",
            "End date",
            "Attendance Target",
            "Total attendees",
            "Status",
        ]

    @property
    def page_context(self):
        context = self.pagination_context
        return context

    @property
    def domain_events(self):
        return domain_events_from_es(self.domain)

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
            'id': event.case_id,
            'name': event.name,
            'start_date': event.start,
            'end_date': event.end,
            'target_attendance': event.attendance_target,
            'total_attendance': event.total_attendance,
            'status': event.status,
        }
