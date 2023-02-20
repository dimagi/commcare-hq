from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.http import HttpResponseRedirect, HttpResponseBadRequest
from django.http import Http404

from corehq.apps.hqwebapp.views import CRUDPaginatedViewMixin
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.events.models import Event
from corehq.apps.events.forms import CreateEventForm
from corehq.apps.hqwebapp.decorators import use_jquery_ui, use_multiselect
from corehq.apps.events.exceptions import EventDoesNotExist
from corehq import toggles
from corehq.apps.users.views import BaseUserSettingsView
from corehq.util.jqueryrmi import JSONResponseMixin
from corehq.apps.users.decorators import require_can_edit_or_view_commcare_users
from django.utils.decorators import method_decorator
from corehq.apps.locations.permissions import location_safe
from django.views.decorators.http import require_GET
from corehq.apps.users.analytics import get_search_users_in_domain_es_query
import json
from corehq.apps.locations.models import SQLLocation
from django.http import JsonResponse

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
        return self.domain_events.count()

    @property
    def column_names(self):
        return [
            _("Name"),
            _("Start date"),
            _("End date"),
            _("Attendance Target"),
            _("Status"),
            _("Total attendees"),
        ]

    @property
    def page_context(self):
        return self.pagination_context

    @property
    def domain_events(self):
        return Event.objects.by_domain(self.domain, most_recent_first=True)

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
            'status': event.status,
            'total_attendance': event.total_attendance or '-',
            'edit_url': reverse(EventEditView.urlname, args=(self.domain, event.event_id)),
        }


class EventCreateView(BaseEventView):
    urlname = 'add_attendance_tracking_event'
    template_name = "new_event.html"

    page_title = _("Add Attendance Tracking Event")

    @use_multiselect
    @use_jquery_ui
    def dispatch(self, request, *args, **kwargs):
        return super(EventCreateView, self).dispatch(request, *args, **kwargs)

    @property
    def page_name(self):
        return _("Add New Event")

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.domain,))

    @property
    def parent_pages(self):
        return [
            {
                'title': _("Events"),
                'url': reverse(EventsView.urlname, args=[self.domain])
            },
        ]

    def get_context_data(self, **kwargs):
        context = super(EventCreateView, self).get_context_data(**kwargs)
        context.update({'form': self.form})
        return context

    def post(self, request, *args, **kwargs):
        form = self.form

        if not form.is_valid():
            return self.get(request, *args, **kwargs)

        event_data = form.cleaned_data

        event = Event(
            name=event_data['name'],
            domain=self.domain,
            start_date=event_data['start_date'],
            end_date=event_data['end_date'],
            attendance_target=event_data['attendance_target'],
            sameday_reg=event_data['sameday_reg'],
            track_each_day=event_data['track_each_day'],
            manager_id=self.request.couch_user.user_id,
        )
        event.save(expected_attendees=event_data['expected_attendees'])

        return HttpResponseRedirect(reverse(EventsView.urlname, args=(self.domain,)))

    @property
    def form(self):
        if self.request.method == 'POST':
            return CreateEventForm(self.request.POST, domain=self.domain)
        else:
            return CreateEventForm(event=self.event, domain=self.domain)

    @property
    def event(self):
        return None


class EventEditView(EventCreateView):
    urlname = 'edit_attendance_tracking_event'
    template_name = "new_event.html"
    http_method_names = ['get', 'post']

    page_title = _("Edit Attendance Tracking Event")
    event_obj = None

    @use_multiselect
    @use_jquery_ui
    def dispatch(self, request, *args, **kwargs):
        self.event_obj = Event.objects.get_event(kwargs['event_id'])
        return super(EventCreateView, self).dispatch(request, *args, **kwargs)

    @property
    def page_name(self):
        return _("Edit Event")

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.domain, self.event.event_id))

    @property
    def event(self):
        if self.event_obj is None:
            raise EventDoesNotExist
        return self.event_obj

    def post(self, request, *args, **kwargs):
        form = self.form

        if not form.is_valid():
            return self.get(request, *args, **kwargs)

        event_update_data = form.cleaned_data

        event = self.event
        event.name = event_update_data['name']
        event.start_date = event_update_data['start_date']
        event.end_date = event_update_data['end_date']
        event.attendance_target = event_update_data['attendance_target']
        event.sameday_reg = event_update_data['sameday_reg']
        event.track_each_day = event_update_data['track_each_day']

        event.save(expected_attendees=event_update_data['expected_attendees'])

        return HttpResponseRedirect(reverse(EventsView.urlname, args=(self.domain,)))


@location_safe
class AttendeesAddView(JSONResponseMixin, BaseUserSettingsView):
    urlname = "add_attendees"
    template_name = 'add_attendees.html'
    page_title = _("Add Attendees")
    limit_text = _("Attendees per page")
    empty_notification = _("You have no attendees")
    loading_message = _("Loading attendees")

    @use_jquery_ui
    @method_decorator(require_can_edit_or_view_commcare_users)
    def dispatch(self, *args, **kwargs):
        return super(AttendeesAddView, self).dispatch(*args, **kwargs)


@require_can_edit_or_view_commcare_users
@require_GET
@location_safe
def paginate_possible_attendees(request, domain):
    """
    Returns the possible attendees (mobile workers).
    """
    # TODO: We should filter for those that does not have an associated `commcare-attendee` case
    limit = int(request.GET.get('limit', 10))
    page = int(request.GET.get('page', 1))
    query = request.GET.get('query')
    deactivated_only = json.loads(request.GET.get('showDeactivatedUsers', "false"))

    def _user_query(search_string, page, limit):
        user_es = get_search_users_in_domain_es_query(
            domain=domain, search_string=search_string,
            offset=page * limit, limit=limit)
        if not request.couch_user.has_permission(domain, 'access_all_locations'):
            loc_ids = (SQLLocation.objects.accessible_to_user(domain, request.couch_user)
                                          .location_ids())
            user_es = user_es.location(list(loc_ids))
        return user_es.mobile_users()

    # backend pages start at 0
    users_query = _user_query(query, page - 1, limit)
    # run with a blank query to fetch total records with same scope as in search
    if deactivated_only:
        users_query = users_query.show_only_inactive()
    users_data = users_query.source([
        '_id',
        'first_name',
        'last_name',
        'base_username',
    ]).run()
    users = users_data.hits

    for user in users:
        user.update({
            'username': user.pop('base_username', ''),
            'user_id': user.pop('_id'),
        })

    return JsonResponse({
        'users': users,
        'total': users_data.total,
    })
