from __future__ import absolute_import
from functools import wraps

from django.db import transaction
from django.http import (
    Http404,
    HttpResponseRedirect,
)
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

from corehq import privileges
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.domain.models import Domain
from corehq.apps.sms.views import BaseMessagingSectionView
from corehq.apps.hqwebapp.async_handler import AsyncHandlerMixin
from corehq.apps.hqwebapp.decorators import use_datatables, use_select2, use_jquery_ui, use_timepicker
from corehq.apps.hqwebapp.views import DataTablesAJAXPaginationMixin
from corehq.apps.translations.models import StandaloneTranslationDoc
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from corehq.messaging.scheduling.async_handlers import MessagingRecipientHandler
from corehq.messaging.scheduling.forms import ScheduleForm, ConditionalAlertForm, ConditionalAlertCriteriaForm
from corehq.messaging.scheduling.models import (
    Schedule,
    AlertSchedule,
    TimedSchedule,
    ImmediateBroadcast,
    ScheduledBroadcast,
    SMSContent,
)
from corehq.messaging.scheduling.exceptions import ImmediateMessageEditAttempt, UnsupportedScheduleError
from corehq.messaging.scheduling.tasks import refresh_alert_schedule_instances, refresh_timed_schedule_instances
from corehq.const import SERVER_DATETIME_FORMAT
from corehq.util.timezones.conversions import ServerTime
from corehq.util.timezones.utils import get_timezone_for_user


def _requires_new_reminder_framework():
    def decorate(fn):
        @wraps(fn)
        def wrapped(request, *args, **kwargs):
            if not hasattr(request, 'project'):
                request.project = Domain.get_by_name(request.domain)
            if request.project.uses_new_reminders:
                return fn(request, *args, **kwargs)
            raise Http404()
        return wrapped
    return decorate


class BroadcastListView(BaseMessagingSectionView, DataTablesAJAXPaginationMixin):
    template_name = 'scheduling/broadcasts_list.html'
    urlname = 'new_list_broadcasts'
    page_title = _('Schedule a Message')

    LIST_SCHEDULED = 'list_scheduled'
    LIST_IMMEDIATE = 'list_immediate'

    @method_decorator(_requires_new_reminder_framework())
    @method_decorator(requires_privilege_with_fallback(privileges.OUTBOUND_SMS))
    @method_decorator(require_permission(Permissions.edit_data))
    @use_datatables
    def dispatch(self, *args, **kwargs):
        return super(BroadcastListView, self).dispatch(*args, **kwargs)

    @cached_property
    def project_timezone(self):
        return get_timezone_for_user(None, self.domain)

    def _format_time(self, time):
        if not time:
            return ''

        user_time = ServerTime(time).user_time(self.project_timezone)
        return user_time.ui_string(SERVER_DATETIME_FORMAT)

    def get_scheduled_ajax_response(self):
        query = (
            ScheduledBroadcast.objects
            .filter(domain=self.domain)
            .order_by('-last_sent_timestamp')
        )
        total_records = query.count()
        query = query.select_related('schedule')
        broadcasts = query[self.display_start:self.display_start + self.display_length]

        data = []
        for broadcast in broadcasts:
            data.append([
                '< delete placeholder >',
                broadcast.name,
                self._format_time(broadcast.last_sent_timestamp),
                broadcast.schedule.active,
                '< action placeholder >',
                broadcast.id,
            ])
        return self.datatables_ajax_response(data, total_records)

    def get_immediate_ajax_response(self):
        query = (
            ImmediateBroadcast.objects
            .filter(domain=self.domain)
            .order_by('-last_sent_timestamp')
        )
        total_records = query.count()
        broadcasts = query[self.display_start:self.display_start + self.display_length]

        data = []
        for broadcast in broadcasts:
            data.append([
                broadcast.name,
                self._format_time(broadcast.last_sent_timestamp),
                broadcast.id,
            ])
        return self.datatables_ajax_response(data, total_records)

    def get(self, request, *args, **kwargs):
        action = request.GET.get('action')
        if action == self.LIST_SCHEDULED:
            return self.get_scheduled_ajax_response()
        elif action == self.LIST_IMMEDIATE:
            return self.get_immediate_ajax_response()

        return super(BroadcastListView, self).get(*args, **kwargs)


class CreateScheduleView(BaseMessagingSectionView, AsyncHandlerMixin):
    urlname = 'create_schedule'
    page_title = _('Schedule a Message')
    template_name = 'scheduling/create_schedule.html'
    async_handlers = [MessagingRecipientHandler]

    @method_decorator(_requires_new_reminder_framework())
    @method_decorator(requires_privilege_with_fallback(privileges.OUTBOUND_SMS))
    @method_decorator(require_permission(Permissions.edit_data))
    @use_jquery_ui
    @use_timepicker
    @use_select2
    def dispatch(self, *args, **kwargs):
        return super(CreateScheduleView, self).dispatch(*args, **kwargs)

    @cached_property
    def project_timezone(self):
        return get_timezone_for_user(None, self.domain)

    @property
    def is_editing(self):
        return False

    @property
    def parent_pages(self):
        return [
            {
                'title': BroadcastListView.page_title,
                'url': reverse(BroadcastListView.urlname, args=[self.domain]),
            },
        ]

    @property
    def form_kwargs(self):
        return {
            'domain': self.domain,
        }

    @cached_property
    def schedule_form(self):
        if self.request.method == 'POST':
            return ScheduleForm(self.request.POST, **self.form_kwargs)
        return ScheduleForm(**self.form_kwargs)

    @property
    def page_context(self):
        return {
            'form': self.schedule_form,
        }

    @cached_property
    def project_languages(self):
        doc = StandaloneTranslationDoc.get_obj(self.domain, 'sms')
        return getattr(doc, 'langs', ['en'])

    def enforce_edit_restriction(self, send_frequency):
        if (
            self.is_editing and
            (send_frequency == ScheduleForm.SEND_IMMEDIATELY or isinstance(self.broadcast, ImmediateBroadcast))
        ):
            raise ImmediateMessageEditAttempt("Cannot edit an immediate message")

    def distill_content(self):
        form_data = self.schedule_form.cleaned_data
        if form_data['translate']:
            messages = {}
            for lang in self.project_languages:
                key = 'message_%s' % lang
                if key in form_data:
                    messages[lang] = form_data[key]
            content = SMSContent(message=messages)
        else:
            content = SMSContent(message={'*': form_data['non_translated_message']})

        return content

    def distill_recipients(self):
        form_data = self.schedule_form.cleaned_data
        return (
            [('CommCareUser', user_id) for user_id in form_data['user_recipients']] +
            [('Group', group_id) for group_id in form_data['user_group_recipients']] +
            [('Location', location_id) for location_id in form_data['user_organization_recipients']] +
            [('CommCareCaseGroup', case_group_id) for case_group_id in form_data['case_group_recipients']]
        )

    def distill_total_iterations(self):
        form_data = self.schedule_form.cleaned_data
        if form_data['stop_type'] == ScheduleForm.STOP_NEVER:
            return TimedSchedule.REPEAT_INDEFINITELY

        return form_data['occurrences']

    def process_immediate_schedule(self, content, recipients, extra_scheduling_options):
        form_data = self.schedule_form.cleaned_data
        with transaction.atomic():
            schedule = AlertSchedule.create_simple_alert(self.domain, content,
                extra_options=extra_scheduling_options)
            broadcast = ImmediateBroadcast(
                domain=self.domain,
                name=form_data['schedule_name'],
                schedule=schedule,
                recipients=recipients,
            )
            broadcast.save()
        refresh_alert_schedule_instances.delay(schedule, recipients)

    def process_daily_schedule(self, content, recipients, extra_scheduling_options):
        form_data = self.schedule_form.cleaned_data
        with transaction.atomic():
            total_iterations = self.distill_total_iterations()

            if self.is_editing:
                broadcast = self.broadcast
                schedule = broadcast.schedule
                schedule.set_simple_daily_schedule(
                    form_data['send_time'],
                    content,
                    total_iterations=total_iterations,
                    extra_options=extra_scheduling_options,
                )
            else:
                schedule = TimedSchedule.create_simple_daily_schedule(
                    self.domain,
                    form_data['send_time'],
                    content,
                    total_iterations=total_iterations,
                    extra_options=extra_scheduling_options,
                )
                broadcast = ScheduledBroadcast(
                    domain=self.domain,
                    schedule=schedule,
                )

            broadcast.name = form_data['schedule_name']
            broadcast.start_date = form_data['start_date']
            broadcast.recipients = recipients
            broadcast.save()
        refresh_timed_schedule_instances.delay(schedule, recipients, start_date=form_data['start_date'])

    def process_weekly_schedule(self, content, recipients, extra_scheduling_options):
        form_data = self.schedule_form.cleaned_data
        with transaction.atomic():
            total_iterations = self.distill_total_iterations()

            if self.is_editing:
                broadcast = self.broadcast
                schedule = broadcast.schedule
                schedule.set_simple_weekly_schedule(
                    form_data['send_time'],
                    content,
                    form_data['weekdays'],
                    form_data['start_date'].weekday(),
                    total_iterations=total_iterations,
                    extra_options=extra_scheduling_options,
                )
            else:
                schedule = TimedSchedule.create_simple_weekly_schedule(
                    self.domain,
                    form_data['send_time'],
                    content,
                    form_data['weekdays'],
                    form_data['start_date'].weekday(),
                    total_iterations=total_iterations,
                    extra_options=extra_scheduling_options,
                )
                broadcast = ScheduledBroadcast(
                    domain=self.domain,
                    schedule=schedule,
                )

            broadcast.name = form_data['schedule_name']
            broadcast.start_date = form_data['start_date']
            broadcast.recipients = recipients
            broadcast.save()
        refresh_timed_schedule_instances.delay(schedule, recipients, start_date=form_data['start_date'])

    def process_monthly_schedule(self, content, recipients, extra_scheduling_options):
        form_data = self.schedule_form.cleaned_data
        with transaction.atomic():
            total_iterations = self.distill_total_iterations()

            positive_days = [day for day in form_data['days_of_month'] if day > 0]
            negative_days = [day for day in form_data['days_of_month'] if day < 0]
            sorted_days_of_month = sorted(positive_days) + sorted(negative_days)

            if self.is_editing:
                broadcast = self.broadcast
                schedule = broadcast.schedule
                schedule.set_simple_monthly_schedule(
                    form_data['send_time'],
                    sorted_days_of_month,
                    content,
                    total_iterations=total_iterations,
                    extra_options=extra_scheduling_options,
                )
            else:
                schedule = TimedSchedule.create_simple_monthly_schedule(
                    self.domain,
                    form_data['send_time'],
                    sorted_days_of_month,
                    content,
                    total_iterations=total_iterations,
                    extra_options=extra_scheduling_options,
                )
                broadcast = ScheduledBroadcast(
                    domain=self.domain,
                    schedule=schedule,
                )

            broadcast.name = form_data['schedule_name']
            broadcast.start_date = form_data['start_date']
            broadcast.recipients = recipients
            broadcast.save()
        refresh_timed_schedule_instances.delay(schedule, recipients, start_date=form_data['start_date'])

    def post(self, request, *args, **kwargs):
        if self.async_response is not None:
            return self.async_response

        if self.schedule_form.is_valid():
            form_data = self.schedule_form.cleaned_data
            self.enforce_edit_restriction(form_data['send_frequency'])
            content = self.distill_content()
            recipients = self.distill_recipients()
            extra_scheduling_options = {
                'include_descendant_locations': (
                    ScheduleForm.RECIPIENT_TYPE_LOCATION in form_data['recipient_types'] and
                    form_data['include_descendant_locations']
                ),
            }

            if form_data['send_frequency'] == ScheduleForm.SEND_IMMEDIATELY:
                self.process_immediate_schedule(content, recipients, extra_scheduling_options)
            elif form_data['send_frequency'] == ScheduleForm.SEND_DAILY:
                self.process_daily_schedule(content, recipients, extra_scheduling_options)
            elif form_data['send_frequency'] == ScheduleForm.SEND_WEEKLY:
                self.process_weekly_schedule(content, recipients, extra_scheduling_options)
            elif form_data['send_frequency'] == ScheduleForm.SEND_MONTHLY:
                self.process_monthly_schedule(content, recipients, extra_scheduling_options)
            return HttpResponseRedirect(reverse(BroadcastListView.urlname, args=[self.domain]))

        return self.get(request, *args, **kwargs)


class EditScheduleView(CreateScheduleView):
    urlname = 'edit_schedule'
    page_title = _('Edit Scheduled Message')

    IMMEDIATE_BROADCAST = 'immediate'
    SCHEDULED_BROADCAST = 'scheduled'

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.broadcast_type, self.broadcast_id])

    @property
    def is_editing(self):
        return True

    @property
    def broadcast_type(self):
        return self.kwargs.get('broadcast_type')

    @cached_property
    def broadcast_class(self):
        if self.broadcast_type == self.IMMEDIATE_BROADCAST:
            return ImmediateBroadcast
        elif self.broadcast_type == self.SCHEDULED_BROADCAST:
            return ScheduledBroadcast
        else:
            raise Http404()

    @property
    def broadcast_id(self):
        return self.kwargs.get('broadcast_id')

    @cached_property
    def broadcast(self):
        try:
            broadcast = self.broadcast_class.objects.prefetch_related('schedule').get(pk=self.broadcast_id)
        except self.broadcast_class.DoesNotExist:
            raise Http404()

        if broadcast.domain != self.domain:
            raise Http404()

        return broadcast

    def get_scheduling_fields_initial(self, broadcast):
        result = {}
        if isinstance(broadcast, ImmediateBroadcast):
            if broadcast.schedule.ui_type == Schedule.UI_TYPE_IMMEDIATE:
                result['send_frequency'] = ScheduleForm.SEND_IMMEDIATELY
            else:
                raise UnsupportedScheduleError(
                    "Unexpected Schedule ui_type '%s' for Schedule '%s'" %
                    (broadcast.schedule.ui_type, broadcast.schedule.schedule_id)
                )
        elif isinstance(broadcast, ScheduledBroadcast):
            schedule = broadcast.schedule
            if schedule.ui_type == Schedule.UI_TYPE_DAILY:
                result['send_frequency'] = ScheduleForm.SEND_DAILY
            elif schedule.ui_type == Schedule.UI_TYPE_WEEKLY:
                weekdays = [(schedule.start_day_of_week + e.day) % 7 for e in schedule.memoized_events]
                result['send_frequency'] = ScheduleForm.SEND_WEEKLY
                result['weekdays'] = [str(day) for day in weekdays]
            elif schedule.ui_type == Schedule.UI_TYPE_MONTHLY:
                result['send_frequency'] = ScheduleForm.SEND_MONTHLY
                result['days_of_month'] = [str(e.day) for e in schedule.memoized_events]
            else:
                raise UnsupportedScheduleError(
                    "Unexpected Schedule ui_type '%s' for Schedule '%s'" % (schedule.ui_type, schedule.schedule_id)
                )

            result['send_time'] = schedule.memoized_events[0].time.strftime('%H:%M')
            result['start_date'] = broadcast.start_date.strftime('%Y-%m-%d')
            if schedule.total_iterations == TimedSchedule.REPEAT_INDEFINITELY:
                result['stop_type'] = ScheduleForm.STOP_NEVER
            else:
                result['stop_type'] = ScheduleForm.STOP_AFTER_OCCURRENCES
                result['occurrences'] = schedule.total_iterations

        return result

    @cached_property
    def schedule_form(self):
        if self.request.method == 'POST':
            return ScheduleForm(self.request.POST, **self.form_kwargs)

        broadcast = self.broadcast
        schedule = broadcast.schedule

        recipient_types = set()
        user_recipients = []
        user_group_recipients = []
        user_organization_recipients = []
        case_group_recipients = []
        for doc_type, doc_id in broadcast.recipients:
            if doc_type == 'CommCareUser':
                recipient_types.add(ScheduleForm.RECIPIENT_TYPE_USER)
                user_recipients.append(doc_id)
            elif doc_type == 'Group':
                recipient_types.add(ScheduleForm.RECIPIENT_TYPE_USER_GROUP)
                user_group_recipients.append(doc_id)
            elif doc_type == 'Location':
                recipient_types.add(ScheduleForm.RECIPIENT_TYPE_LOCATION)
                user_organization_recipients.append(doc_id)
            elif doc_type == 'CommCareCaseGroup':
                recipient_types.add(ScheduleForm.RECIPIENT_TYPE_CASE_GROUP)
                case_group_recipients.append(doc_id)

        initial = {
            'schedule_name': broadcast.name,
            'recipient_types': list(recipient_types),
            'user_recipients': ','.join(user_recipients),
            'user_group_recipients': ','.join(user_group_recipients),
            'user_organization_recipients': ','.join(user_organization_recipients),
            'case_group_recipients': ','.join(case_group_recipients),
            'include_descendant_locations': broadcast.schedule.include_descendant_locations,
            'content': 'sms',
            # only works for SMS
            'message': schedule.memoized_events[0].content.message,
        }
        initial.update(self.get_scheduling_fields_initial(broadcast))
        return ScheduleForm(initial=initial, **self.form_kwargs)


class ConditionalAlertListView(BaseMessagingSectionView, DataTablesAJAXPaginationMixin):
    template_name = 'scheduling/conditional_alert_list.html'
    urlname = 'conditional_alert_list'
    page_title = _('Schedule a Conditional Message')

    @method_decorator(_requires_new_reminder_framework())
    @method_decorator(requires_privilege_with_fallback(privileges.OUTBOUND_SMS))
    @method_decorator(require_permission(Permissions.edit_data))
    @use_datatables
    def dispatch(self, *args, **kwargs):
        return super(ConditionalAlertListView, self).dispatch(*args, **kwargs)


class CreateConditionalAlertView(BaseMessagingSectionView, AsyncHandlerMixin):
    urlname = 'create_conditional_alert'
    page_title = _('New Conditional Message')
    template_name = 'scheduling/conditional_alert.html'
    async_handlers = [MessagingRecipientHandler]

    @method_decorator(_requires_new_reminder_framework())
    @method_decorator(requires_privilege_with_fallback(privileges.OUTBOUND_SMS))
    @method_decorator(require_permission(Permissions.edit_data))
    @use_jquery_ui
    @use_timepicker
    @use_select2
    def dispatch(self, *args, **kwargs):
        return super(CreateConditionalAlertView, self).dispatch(*args, **kwargs)

    @property
    def parent_pages(self):
        return [
            {
                'title': ConditionalAlertListView.page_title,
                'url': reverse(ConditionalAlertListView.urlname, args=[self.domain]),
            },
        ]

    @property
    def page_context(self):
        return {
            'basic_info_form': self.basic_info_form,
            'criteria_form': self.criteria_form,
        }

    @property
    def initial_rule(self):
        return None

    @cached_property
    def read_only_mode(self):
        return (
            not self.is_system_admin and
            self.criteria_form.requires_system_admin_to_edit
        )

    @cached_property
    def is_system_admin(self):
        return self.request.couch_user.is_superuser

    @cached_property
    def basic_info_form(self):
        if self.request.method == 'POST':
            return ConditionalAlertForm(self.domain, self.request.POST)

        return ConditionalAlertForm(self.domain)

    @cached_property
    def criteria_form(self):
        kwargs = {
            'rule': self.initial_rule,
            'is_system_admin': self.is_system_admin,
        }

        if self.request.method == 'POST':
            return ConditionalAlertCriteriaForm(self.domain, self.request.POST, **kwargs)

        return ConditionalAlertCriteriaForm(self.domain, **kwargs)

    def post(self, request, *args, **kwargs):
        basic_info_form_valid = self.basic_info_form.is_valid()
        criteria_form_valid = self.criteria_form.is_valid()

        if self.read_only_mode:
            # Don't allow making changes to rules that have custom
            # criteria/actions unless the user has permission to
            return HttpResponseBadRequest()

        if basic_info_form_valid and criteria_form_valid:
            if not self.is_system_admin and self.criteria_form.requires_system_admin_to_save:
                # Don't allow adding custom criteria/actions to rules
                # unless the user has permission to
                return HttpResponseBadRequest()

            with transaction.atomic():
                if self.initial_rule:
                    rule = self.initial_rule
                else:
                    rule = AutomaticUpdateRule(
                        domain=self.domain,
                        active=True,
                        migrated=True,
                        workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING,
                    )

                rule.name = self.basic_info_form.cleaned_data['name']
                self.criteria_form.save_criteria(rule)
            return HttpResponseRedirect(reverse(ConditionalAlertListView.urlname, args=[self.domain]))

        return self.get(request, *args, **kwargs)


class EditConditionalAlertView(CreateConditionalAlertView):
    urlname = 'edit_conditional_alert'
    page_title = _('Edit Conditional Message')
