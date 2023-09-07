from django.http import Http404, HttpResponseRedirect, JsonResponse, HttpResponseServerError
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_GET
from django.shortcuts import render

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
from corehq.apps.users.dbaccessors import (
    get_all_commcare_users_by_domain,
    get_mobile_users_by_filters
)
from .exceptions import AttendeeTrackedException
from soil.util import expose_cached_download, get_download_context
from soil.exceptions import TaskFailedError
from dimagi.utils.logging import notify_exception

from .forms import EditAttendeeForm, EventForm, NewAttendeeForm
from .models import (
    ATTENDED_DATE_CASE_PROPERTY,
    EVENT_IN_PROGRESS,
    EVENT_NOT_STARTED,
    EVENT_STATUS_TRANS,
    LOCATION_IDS_CASE_PROPERTY,
    PRIMARY_LOCATION_ID_CASE_PROPERTY,
    AttendeeModel,
    Event,
    get_attendee_case_type,
    mobile_worker_attendees_enabled,
)
from .es import get_paginated_attendees
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
            _("Location"),
            _("Attendance Target"),
            _("Status"),
            _("Total attendance"),
            _("Total attendance takers"),
            _("Attendees"),
        ]

    @property
    def page_context(self):
        return self.pagination_context

    @property
    def domain_events(self):
        return Event.objects.by_domain(self.domain, not_started_first=True)

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
            'location': event.location.name if event.location else '',
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
            location_id=event_data['location_id'] or None,
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
        try:
            self.event_obj = Event.objects.get(
                domain=self.domain,
                event_id=kwargs['event_id'],
            )
        except Event.DoesNotExist:
            raise Http404()
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
        event.location_id = event_update_data['location_id']
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
    def page_context(self):
        context = super().page_context
        if self.request.method == "POST":
            form = NewAttendeeForm(self.request.POST, domain=self.domain)
        else:
            form = NewAttendeeForm(domain=self.domain)
        return context | {'new_attendee_form': form}

    @allow_remote_invocation
    def create_attendee(self, data):
        form_data = data['attendee'] | {
            'domain': self.domain,
        }
        form = NewAttendeeForm(form_data, domain=self.domain)
        if form.is_valid():
            if form.cleaned_data['location_id']:
                properties = {
                    LOCATION_IDS_CASE_PROPERTY:
                        form.cleaned_data['location_id'],
                    PRIMARY_LOCATION_ID_CASE_PROPERTY:
                        form.cleaned_data['location_id'],
                }
            else:
                properties = {}
            helper = CaseHelper(domain=self.domain)
            helper.create_case({
                'case_type': get_attendee_case_type(self.domain),
                'case_name': form.cleaned_data['name'],
                'owner_id': self.request.couch_user.user_id,
                'properties': properties,
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
            'attendee_name': instance.name,
            'attendee_has_attended_events': instance.has_attended_events(),
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


class AttendeeDeleteView(BaseEventView):
    urlname = 'delete_attendee'

    def post(self, request, domain, attendee_id):
        instance = AttendeeModel.objects.get(
            case_id=attendee_id,
            domain=domain
        )
        try:
            instance.delete()
        except AttendeeTrackedException:
            return JsonResponse({
                'failed': 'Cannot delete an attendee that has been tracked in one or more events.'
            }, status=400)

        return HttpResponseRedirect(reverse(AttendeesListView.urlname, args=(domain,)))


class AttendeesConfigView(JSONResponseMixin, BaseUserSettingsView, BaseEventView):
    urlname = "attendees_config"

    @allow_remote_invocation
    def get(self, request, *args, **kwargs):
        return self.json_response({
            'mobile_worker_attendee_enabled': mobile_worker_attendees_enabled(self.domain)
        })


class ConvertMobileWorkerAttendeesView(BaseUserSettingsView, BaseEventView):
    urlname = "convert_mobile_workers"

    @allow_remote_invocation
    def get(self, request, *args, **kwargs):
        task_ref = expose_cached_download(
            payload=None, expiry=60 * 60, file_extension=None
        )
        if not mobile_worker_attendees_enabled(self.domain):
            task = sync_mobile_worker_attendees.delay(self.domain, user_id=self.couch_user.user_id)
        else:
            task = close_mobile_worker_attendee_cases.delay(self.domain)

        task_ref.set_task(task)
        return HttpResponseRedirect(
            reverse(
                MobileWorkerAttendeeSatusView.urlname,
                args=[self.domain, task_ref.download_id]
            )
        )


class MobileWorkerAttendeeSatusView(BaseEventView):
    urlname = "convert_mobile_worker_status"

    @property
    def page_title(self):
        if mobile_worker_attendees_enabled(self.domain):
            return _("Enabling mobile worker attendees status")
        else:
            return _("Disabling mobile worker attendees status")

    @property
    def parent_pages(self):
        return [{
            'title': AttendeesListView.page_title,
            'url': reverse(AttendeesListView.urlname, args=[self.domain]),
        }]

    def get(self, request, *args, **kwargs):
        context = super(MobileWorkerAttendeeSatusView, self).main_context
        context.update({
            'domain': self.domain,
            'download_id': kwargs['download_id'],
            'poll_url': reverse('poll_mobile_worker_attendee_progress', args=[self.domain, kwargs['download_id']]),
            'title': _(self.page_title),
            'progress_text': _("Processing Mobile Workers. This may take some time..."),
            'error_text': _("User conversion failed for some reason and we have noted this failure."),
            'next_url': reverse(AttendeesListView.urlname, args=[self.domain]),
            'next_url_text': _("Go back to view attendees"),
        })
        return render(request, 'hqwebapp/bootstrap3/soil_status_full.html', context)

    def page_url(self):
        return reverse(self.urlname, args=self.args, kwargs=self.kwargs)


@require_GET
@login_and_domain_required
def poll_mobile_worker_attendee_progress(request, domain, download_id):
    try:
        context = get_download_context(download_id, require_result=False)
    except TaskFailedError as e:
        notify_exception(request, message=str(e))
        return HttpResponseServerError()

    if mobile_worker_attendees_enabled(domain):
        context.update({
            'on_complete_long': _("Mobile workers can now also be selected to attend events."),
            'on_complete_short': _("Enabling mobile workers complete!"),
            'custom_message': _("Enabling mobile worker attendees in progress. This may take a while..."),
        })
    else:
        context.update({
            'on_complete_long': _("Mobile workers are now removed from the potential attendees list."),
            'on_complete_short': _("Disabling mobile workers complete!"),
            'custom_message': _("Disabling mobile worker attendees in progress. This may take a while..."),
        })

    template = "partials/attendee_conversion_status.html"
    return render(request, template, context)


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


@require_GET
@login_and_domain_required
@require_permission(HqPermissions.manage_attendance_tracking)
def get_attendees_and_attendance_takers(request, domain):
    location_id = request.GET.get('location_id', None)
    attendance_takers_filters = {'user_active_status': True}
    if location_id:
        attendees = AttendeeModel.objects.by_location_id(domain=domain, location_id=location_id)
        attendance_takers_filters['location_id'] = location_id
    else:
        attendees = AttendeeModel.objects.by_domain(domain=domain)

    attendance_takers = get_mobile_users_by_filters(domain, attendance_takers_filters)
    attendees_list = [
        {'id': attendee.case_id, 'name': attendee.name}
        for attendee in attendees
    ]
    attendance_takers_list = [
        {'id': attendance_taker.user_id, 'name': attendance_taker.raw_username}
        for attendance_taker in attendance_takers
    ]

    return JsonResponse({
        'attendees': attendees_list,
        'attendance_takers': attendance_takers_list
    })
