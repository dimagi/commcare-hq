import json

from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_GET

from memoized import memoized

from corehq import toggles
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.hqcase.case_helper import CaseHelper
from corehq.apps.hqwebapp.decorators import use_jquery_ui, use_multiselect
from corehq.apps.hqwebapp.views import CRUDPaginatedViewMixin
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import HqPermissions
from corehq.apps.users.views import BaseUserSettingsView
from corehq.util.jqueryrmi import JSONResponseMixin, allow_remote_invocation

from .forms import EditAttendeeForm, EventForm, NewAttendeeForm
from .models import (
    ATTENDED_DATE_CASE_PROPERTY,
    EVENT_IN_PROGRESS,
    EVENT_NOT_STARTED,
    EVENT_STATUS_TRANS,
    AttendeeModel,
    Event,
    get_attendee_case_type,
    get_paginated_attendees,
    mobile_worker_attendees_enabled,
    toggle_mobile_worker_attendees,
)
from .tasks import (
    close_mobile_worker_attendee_cases,
    sync_mobile_worker_attendees,
)


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
            _("Total attendance"),
            _("Total attendance takers"),
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
        events = self.domain_events[start:end]
        for event in events:
            event.save(update_fields=['attendee_list_status'])

        for event in self.domain_events[start:end]:
            yield {
                'itemData': self._format_paginated_event(event),
                'template': 'base-event-template'
            }

    def post(self, *args, **kwargs):
        return self.paginate_crud_response

    def _format_paginated_event(self, event: Event):
        attendees = event.get_attended_attendees()
        attendees = sorted(
            attendees,
            key=lambda attendee: (
                attendee.get_case_property(ATTENDED_DATE_CASE_PROPERTY),
                attendee.name
            )
        )
        attendees = [
            {
                'date': attendee.get_case_property(ATTENDED_DATE_CASE_PROPERTY),
                'name': attendee.name
            }
            for attendee in attendees
        ]
        return {
            'id': event.event_id.hex,
            'name': event.name,
            # dates are not serializable for django templates
            'start_date': str(event.start_date),
            'end_date': str(event.end_date) if event.end_date else '-',
            'is_editable': event.status in (EVENT_NOT_STARTED, EVENT_IN_PROGRESS),
            'show_attendance': event.status != EVENT_NOT_STARTED,
            'target_attendance': event.attendance_target,
            'status': EVENT_STATUS_TRANS[event.status],
            'total_attendance': event.total_attendance or '-',
            'attendees': attendees,
            'edit_url': reverse(EventEditView.urlname, args=(self.domain, event.event_id)),
            'total_attendance_takers': event.get_total_attendance_takers() or '-'
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
        context = super().get_context_data(**kwargs)
        if self.request.method == 'POST':
            context['form'] = EventForm(self.request.POST, domain=self.domain)
        else:
            context['form'] = EventForm(event=self.event, domain=self.domain)
        return context

    def post(self, request, *args, **kwargs):
        form = EventForm(self.request.POST, domain=self.domain)

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
            attendance_taker_ids=event_data.get('attendance_takers', None),
        )
        event.save()
        event.set_expected_attendees(event_data['expected_attendees'])

        return HttpResponseRedirect(reverse(EventsView.urlname, args=(self.domain,)))

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
        self.event_obj = Event.objects.get(
            domain=self.domain,
            event_id=kwargs['event_id'],
        )
        return super().dispatch(request, *args, **kwargs)

    @property
    def page_name(self):
        return _("Edit Event")

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.domain, self.event.event_id.hex))

    @property
    def event(self):
        if self.event_obj is None:
            raise Event.DoesNotExist
        return self.event_obj

    def post(self, request, *args, **kwargs):
        form = EventForm(self.request.POST, domain=self.domain, event=self.event)

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
        event.attendance_taker_ids = event_update_data['attendance_takers']
        event.save()
        event.set_expected_attendees(event_update_data['expected_attendees'])

        return HttpResponseRedirect(reverse(EventsView.urlname, args=(self.domain,)))


class AttendeesListView(JSONResponseMixin, BaseEventView):
    urlname = "event_attendees"
    template_name = 'event_attendees.html'
    page_title = _("Attendees")

    limit_text = _("Attendees per page")
    empty_notification = _("You have no attendees")
    loading_message = _("Loading attendees")

    @use_jquery_ui
    def dispatch(self, *args, **kwargs):
        # The FF check is temporary till the full feature is released
        toggle_enabled = toggles.ATTENDANCE_TRACKING.enabled(self.domain)
        if not (self.request.couch_user.can_manage_events(self.domain) and toggle_enabled):
            raise Http404
        return super(AttendeesListView, self).dispatch(*args, **kwargs)

    @property
    @memoized
    def new_attendee_form(self):
        if self.request.method == "POST":
            return NewAttendeeForm(self.request.POST)
        return NewAttendeeForm()

    @property
    def page_context(self):
        return {
            'new_attendee_form': self.new_attendee_form,
        }

    @allow_remote_invocation
    def create_attendee(self, data):
        form_data = data['attendee'] | {
            'domain': self.domain,
        }
        form = NewAttendeeForm(form_data)
        if form.is_valid():
            helper = CaseHelper(domain=self.domain)
            helper.create_case({
                'case_type': get_attendee_case_type(self.domain),
                'case_name': form.cleaned_data['name'],
                'owner_id': self.request.couch_user.user_id,
            })
            return {
                'success': True,
                'case_id': helper.case.case_id,
            }

        err = ', '.join([e for errors in form.errors.values() for e in errors])
        return {'error': _("Form validation failed: {}").format(err)}


class AttendeeEditView(BaseEventView):
    urlname = 'edit_attendee'
    template_name = "edit_attendee.html"

    page_title = _("Edit Attendee")

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.domain, self.attendee_id))

    @use_multiselect
    @use_jquery_ui
    def dispatch(self, request, *args, **kwargs):
        self.attendee_id = kwargs['attendee_id']
        return super().dispatch(request, *args, **kwargs)

    @property
    def parent_pages(self):
        return [{
            'title': AttendeesListView.page_title,
            'url': reverse(AttendeesListView.urlname, args=(self.domain,))
        }]

    @property
    def page_context(self):
        context = super().page_context
        instance = AttendeeModel.objects.get(
            case_id=self.attendee_id,
            domain=self.domain,
        )
        if self.request.method == 'POST':
            form = EditAttendeeForm(
                self.request.POST,
                domain=self.domain,
                instance=instance,
            )
        else:
            form = EditAttendeeForm(domain=self.domain, instance=instance)
        context.update({
            'attendee_id': self.attendee_id,
            'form': form,
        })
        return context

    def post(self, request, *args, **kwargs):
        instance = AttendeeModel.objects.get(
            case_id=kwargs['attendee_id'],
            domain=self.domain,
        )
        form = EditAttendeeForm(
            self.request.POST,
            domain=self.domain,
            instance=instance,
        )
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(
                reverse(AttendeesListView.urlname, args=(self.domain,))
            )
        return self.get(request, *args, **kwargs)


class AttendeesConfigView(JSONResponseMixin, BaseUserSettingsView, BaseEventView):
    urlname = "attendees_config"

    @allow_remote_invocation
    def get(self, request, *args, **kwargs):
        return self.json_response({
            "mobile_worker_attendee_enabled": mobile_worker_attendees_enabled(self.domain)
        })

    @allow_remote_invocation
    def post(self, request, *args, **kwargs):
        json_data = json.loads(request.body)
        attendees_enabled = json_data['mobile_worker_attendee_enabled']
        toggle_mobile_worker_attendees(self.domain, attendees_enabled)
        if attendees_enabled:
            sync_mobile_worker_attendees.delay(self.domain, user_id=self.couch_user.user_id)
        else:
            close_mobile_worker_attendee_cases.delay(self.domain)

        return self.json_response({
            "mobile_worker_attendee_enabled": attendees_enabled
        })


@require_GET
@login_and_domain_required
@require_permission(HqPermissions.manage_attendance_tracking)
def paginated_attendees(request, domain):
    """
    Returns the possible attendees.
    """
    limit = int(request.GET.get('limit', 10))
    page = int(request.GET.get('page', 1))
    query = request.GET.get('query')

    cases, total = get_paginated_attendees(
        domain=domain,
        limit=limit,
        page=page,
        query=query
    )

    return JsonResponse({
        'attendees': [{'case_id': c.case_id, 'name': c.name} for c in cases],
        'total': total,
    })
