import io
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    JsonResponse,
)
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from six.moves.urllib.parse import quote_plus

from couchexport.export import export_raw
from couchexport.models import Format
from couchexport.shortcuts import export_response
from dimagi.utils.couch import CriticalSection
from dimagi.utils.parsing import json_format_date

from corehq import privileges
from corehq.apps.accounting.decorators import (
    requires_privilege_json_response,
    requires_privilege_with_fallback,
)
from corehq.apps.data_dictionary.util import get_data_dict_props_by_case_type
from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.hqwebapp.async_handler import AsyncHandlerMixin
from corehq.apps.hqwebapp.decorators import (
    use_datatables,
    use_jquery_ui,
    use_nvd3,
    use_timepicker,
)
from corehq.apps.hqwebapp.utils import get_bulk_upload_form
from corehq.apps.sms.filters import EventStatusFilter, EventTypeFilter
from corehq.apps.sms.models import (
    INCOMING,
    OUTGOING,
    SMS,
    MessagingEvent,
    QueuedSMS,
)
from corehq.apps.sms.tasks import OutboundDailyCounter, time_within_windows
from corehq.apps.sms.views import BaseMessagingSectionView
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import HqPermissions
from corehq.blobs.exceptions import NotFound
from corehq.const import SERVER_DATETIME_FORMAT
from corehq.messaging.scheduling.async_handlers import (
    ConditionalAlertAsyncHandler,
    MessagingRecipientHandler,
)
from corehq.messaging.scheduling.const import (
    MAX_IMAGE_UPLOAD_SIZE,
    VALID_EMAIL_IMAGE_MIMETYPES,
)
from corehq.messaging.scheduling.forms import (
    BroadcastForm,
    ConditionalAlertCriteriaForm,
    ConditionalAlertForm,
    ConditionalAlertScheduleForm,
)
from corehq.messaging.scheduling.models import (
    AlertSchedule,
    ImmediateBroadcast,
    ScheduledBroadcast,
    TimedSchedule,
)
from corehq.messaging.scheduling.models.content import EmailImage
from corehq.messaging.scheduling.scheduling_partitioned.dbaccessors import (
    get_count_of_active_schedule_instances_due,
)
from corehq.messaging.scheduling.tasks import (
    refresh_alert_schedule_instances,
    refresh_timed_schedule_instances,
)
from corehq.messaging.scheduling.view_helpers import (
    TranslatedConditionalAlertUploader,
    UntranslatedConditionalAlertUploader,
    get_conditional_alert_headers,
    get_conditional_alert_rows,
    get_conditional_alerts_queryset_by_domain,
    upload_conditional_alert_workbook,
)
from corehq.messaging.tasks import initiate_messaging_rule_run
from corehq.messaging.util import MessagingRuleProgressHelper
from corehq.toggles import RICH_TEXT_EMAILS
from corehq.util.timezones.conversions import ServerTime
from corehq.util.timezones.utils import get_timezone_for_user
from corehq.util.view_utils import absolute_reverse
from corehq.util.workbook_json.excel import WorkbookJSONError, get_workbook


def get_broadcast_edit_critical_section(broadcast_type, broadcast_id):
    return CriticalSection(['edit-broadcast-%s-%s' % (broadcast_type, broadcast_id)], timeout=5 * 60)


def get_conditional_alert_edit_critical_section(rule_id):
    return CriticalSection(['edit-conditional-alert-%s' % rule_id], timeout=5 * 60)


class MessagingDashboardView(BaseMessagingSectionView):
    urlname = 'messaging_dashboard'
    page_title = gettext_lazy("Dashboard")
    template_name = 'scheduling/dashboard.html'

    @use_nvd3
    def dispatch(self, *args, **kwargs):
        return super(MessagingDashboardView, self).dispatch(*args, **kwargs)

    def get_messaging_history_errors_url(self, messaging_history_url):
        url_param_tuples = [
            ('startdate', (self.domain_now.date() - timedelta(days=6)).strftime('%Y-%m-%d')),
            ('enddate', self.domain_now.date().strftime('%Y-%m-%d')),
            (EventStatusFilter.slug, MessagingEvent.STATUS_ERROR),
        ]

        for event_type, description in EventTypeFilter.options:
            url_param_tuples.append((EventTypeFilter.slug, event_type))

        url_param_list = ['%s=%s' % (quote_plus(name), quote_plus(value)) for name, value in url_param_tuples]
        url_param_str = '&'.join(url_param_list)

        return '%s?%s' % (messaging_history_url, url_param_str)

    @property
    def page_context(self):
        from corehq.apps.reports.standard.sms import (
            MessageLogReport,
            MessagingEventsReport,
            ScheduleInstanceReport,
        )

        scheduled_events_url = reverse(ScheduleInstanceReport.dispatcher.name(), args=[],
            kwargs={'domain': self.domain, 'report_slug': ScheduleInstanceReport.slug})

        context = super().page_context
        context.update({
            'scheduled_events_url': scheduled_events_url,
            'message_log_url': reverse(
                MessageLogReport.dispatcher.name(), args=[],
                kwargs={'domain': self.domain, 'report_slug': MessageLogReport.slug}
            ),
            'messaging_history_url': reverse(
                MessagingEventsReport.dispatcher.name(), args=[],
                kwargs={'domain': self.domain, 'report_slug': MessagingEventsReport.slug}
            ),
        })

        context['messaging_history_errors_url'] = self.get_messaging_history_errors_url(
            context['messaging_history_url']
        )

        return context

    @cached_property
    def timezone(self):
        return self.domain_object.get_default_timezone()

    @cached_property
    def domain_now(self):
        return ServerTime(datetime.utcnow()).user_time(self.timezone).done()

    def add_sms_status_info(self, result):
        if len(self.domain_object.restricted_sms_times) > 0:
            result['uses_restricted_time_windows'] = True
            sms_allowed = result['within_allowed_sms_times'] = time_within_windows(
                self.domain_now,
                self.domain_object.restricted_sms_times
            )
            # find next restricted window transition
            for i in range(1, 7 * 24 * 60):
                # This is a very fast check so it's ok to iterate this many times.
                future_time = self.domain_now + timedelta(minutes=i)
                future_allowed = time_within_windows(future_time, self.domain_object.restricted_sms_times)
                if sms_allowed != future_allowed:
                    result['sms_resume_time'] = future_time.strftime('%Y-%m-%d %H:%M')
                    break
        else:
            result['uses_restricted_time_windows'] = False
            result['within_allowed_sms_times'] = True

        result.update({
            'queued_sms_count': QueuedSMS.objects.filter(domain=self.domain).count(),
            'outbound_sms_sent_today': OutboundDailyCounter(self.domain_object).current_usage,
            'daily_outbound_sms_limit': self.domain_object.get_daily_outbound_sms_limit(),
        })

    def add_reminder_status_info(self, result):
        events_pending = get_count_of_active_schedule_instances_due(self.domain, datetime.utcnow())
        result['events_pending'] = events_pending

    def add_sms_count_info(self, result, days):
        end_date = self.domain_now.date()
        start_date = end_date - timedelta(days=days - 1)
        counts = SMS.get_counts_by_date(self.domain, start_date, end_date, self.timezone.zone)

        inbound_counts = {}
        outbound_counts = {}

        for row in counts:
            if row.direction == INCOMING:
                inbound_counts[row.date] = row.sms_count
            elif row.direction == OUTGOING:
                outbound_counts[row.date] = row.sms_count

        inbound_values = []
        outbound_values = []

        for i in range(days):
            dt = start_date + timedelta(days=i)
            inbound_values.append({
                'x': dt.strftime('%Y-%m-%d'),
                'y': inbound_counts.get(dt, 0),
            })
            outbound_values.append({
                'x': dt.strftime('%Y-%m-%d'),
                'y': outbound_counts.get(dt, 0),
            })

        result['sms_count_data'] = [
            {'key': _("Incoming"), 'values': inbound_values},
            {'key': _("Outgoing"), 'values': outbound_values},
        ]

    def add_event_count_info(self, result, days):
        end_date = self.domain_now.date()
        start_date = end_date - timedelta(days=days - 1)
        counts = MessagingEvent.get_counts_by_date(self.domain, start_date, end_date, self.timezone.zone)

        counts_dict = {
            row.date: {'error': row.error_count, 'total': row.total_count}
            for row in counts
        }

        error_values = []
        success_values = []

        for i in range(days):
            dt = start_date + timedelta(days=i)
            error_count = counts_dict.get(dt, {}).get('error', 0)
            total_count = counts_dict.get(dt, {}).get('total', 0)

            error_values.append({
                'x': dt.strftime('%Y-%m-%d'),
                'y': error_count,
            })
            success_values.append({
                'x': dt.strftime('%Y-%m-%d'),
                'y': total_count - error_count,
            })

        result['event_count_data'] = [
            {'key': _("Error"), 'values': error_values},
            {'key': _("Success"), 'values': success_values},
        ]

    def get_error_message(self, error_code):
        if error_code in SMS.ERROR_MESSAGES:
            return _(SMS.ERROR_MESSAGES[error_code])
        elif error_code in MessagingEvent.ERROR_MESSAGES:
            return _(MessagingEvent.ERROR_MESSAGES[error_code])
        else:
            return _("Other")

    def add_error_count_info(self, result, days):
        end_date = self.domain_now.date()
        start_date = end_date - timedelta(days=days - 1)
        counts = MessagingEvent.get_counts_of_errors(self.domain, start_date, end_date, self.timezone.zone)

        # Consolidate opt-out errors so they show up as one bar in the graph
        if SMS.ERROR_PHONE_NUMBER_OPTED_OUT in counts and MessagingEvent.ERROR_PHONE_OPTED_OUT in counts:
            counts[MessagingEvent.ERROR_PHONE_OPTED_OUT] += counts[SMS.ERROR_PHONE_NUMBER_OPTED_OUT]
            del counts[SMS.ERROR_PHONE_NUMBER_OPTED_OUT]

        sorted_counts = sorted(counts.items(), key=lambda item: item[1], reverse=True)
        result['error_count_data'] = [
            {
                'values': [
                    {'label': self.get_error_message(error), 'value': count}
                    for error, count in sorted_counts
                ],
            },
        ]

    def get_ajax_response(self):
        result = {
            'last_refresh_time': self.domain_now.strftime('%Y-%m-%d %H:%M:%S'),
            'project_timezone': self.timezone.zone,
        }
        self.add_sms_status_info(result)
        self.add_reminder_status_info(result)
        self.add_sms_count_info(result, 30)
        self.add_event_count_info(result, 30)
        self.add_error_count_info(result, 30)
        return JsonResponse(result)

    def get(self, request, *args, **kwargs):
        if request.GET.get('action') == 'raw':
            return self.get_ajax_response()

        return super(MessagingDashboardView, self).get(request, *args, **kwargs)


class BroadcastListView(BaseMessagingSectionView):
    template_name = 'scheduling/broadcasts_list.html'
    urlname = 'new_list_broadcasts'
    page_title = gettext_lazy('Broadcasts')

    LIST_SCHEDULED = 'list_scheduled'
    LIST_IMMEDIATE = 'list_immediate'
    ACTION_ACTIVATE_SCHEDULED_BROADCAST = 'activate_scheduled_broadcast'
    ACTION_DEACTIVATE_SCHEDULED_BROADCAST = 'deactivate_scheduled_broadcast'
    ACTION_DELETE_SCHEDULED_BROADCAST = 'delete_scheduled_broadcast'

    @method_decorator(requires_privilege_with_fallback(privileges.REMINDERS_FRAMEWORK))
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
            .filter(domain=self.domain, deleted=False)
            .order_by('-last_sent_timestamp', 'id')
        )
        total_records = query.count()
        query = query.select_related('schedule')
        limit = int(self.request.GET.get('limit', 10))
        page = int(self.request.GET.get('page', 1))
        skip = (page - 1) * limit

        broadcasts = [self._fmt_scheduled_broadcast(broadcast) for broadcast in query[skip:skip + limit]]
        return JsonResponse({
            'broadcasts': broadcasts,
            'total': total_records,
        })

    def _fmt_scheduled_broadcast(self, broadcast):
        return {
            'name': broadcast.name,
            'last_sent': self._format_time(broadcast.last_sent_timestamp),
            'active': broadcast.schedule.active,
            'editable': self.can_use_inbound_sms or not broadcast.schedule.memoized_uses_sms_survey,
            'id': broadcast.id,
            'deleted': broadcast.deleted,
        }

    def get_immediate_ajax_response(self):
        query = (
            ImmediateBroadcast.objects
            .filter(domain=self.domain, deleted=False)
            .order_by('-last_sent_timestamp', 'id')
        )
        total_records = query.count()
        limit = int(self.request.GET.get('limit', 10))
        page = int(self.request.GET.get('page', 1))
        skip = (page - 1) * limit

        broadcasts = [{
            'name': broadcast.name,
            'last_sent': self._format_time(broadcast.last_sent_timestamp),
            'id': broadcast.id,
        } for broadcast in query[skip:skip + limit]]

        return JsonResponse({
            'broadcasts': broadcasts,
            'total': total_records,
        })

    def get_scheduled_broadcast(self, broadcast_id):
        try:
            return ScheduledBroadcast.objects.get(domain=self.domain, pk=broadcast_id, deleted=False)
        except ScheduledBroadcast.DoesNotExist:
            raise Http404()

    def get_scheduled_broadcast_activate_ajax_response(self, active_flag, broadcast_id):
        broadcast = self.get_scheduled_broadcast(broadcast_id)
        if not self.can_use_inbound_sms and broadcast.schedule.memoized_uses_sms_survey:
            return HttpResponseBadRequest(
                "Cannot create or edit survey reminders because subscription "
                "does not have access to inbound SMS"
            )

        TimedSchedule.objects.filter(schedule_id=broadcast.schedule_id).update(active=active_flag)
        refresh_timed_schedule_instances.delay(
            broadcast.schedule_id.hex,
            broadcast.recipients,
            start_date_iso_string=json_format_date(broadcast.start_date)
        )

        return JsonResponse({
            'success': True,
            'broadcast': self._fmt_scheduled_broadcast(broadcast),
        })

    def get_scheduled_broadcast_delete_ajax_response(self, broadcast_id):
        broadcast = self.get_scheduled_broadcast(broadcast_id)
        broadcast.soft_delete()
        return JsonResponse({
            'success': True,
            'broadcast': self._fmt_scheduled_broadcast(broadcast),
        })

    def get(self, request, *args, **kwargs):
        action = request.GET.get('action')
        if action == self.LIST_SCHEDULED:
            return self.get_scheduled_ajax_response()
        elif action == self.LIST_IMMEDIATE:
            return self.get_immediate_ajax_response()

        return super(BroadcastListView, self).get(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        broadcast_id = request.POST.get('broadcast_id')

        with get_broadcast_edit_critical_section(EditScheduleView.SCHEDULED_BROADCAST, broadcast_id):
            if action == self.ACTION_ACTIVATE_SCHEDULED_BROADCAST:
                return self.get_scheduled_broadcast_activate_ajax_response(True, broadcast_id)
            elif action == self.ACTION_DEACTIVATE_SCHEDULED_BROADCAST:
                return self.get_scheduled_broadcast_activate_ajax_response(False, broadcast_id)
            elif action == self.ACTION_DELETE_SCHEDULED_BROADCAST:
                return self.get_scheduled_broadcast_delete_ajax_response(broadcast_id)
            else:
                return HttpResponseBadRequest()


class CreateScheduleView(BaseMessagingSectionView, AsyncHandlerMixin):
    urlname = 'create_schedule'
    page_title = gettext_lazy('New Broadcast')
    template_name = 'scheduling/create_schedule.html'
    async_handlers = [MessagingRecipientHandler]
    read_only_mode = False

    @method_decorator(requires_privilege_with_fallback(privileges.REMINDERS_FRAMEWORK))
    @use_jquery_ui
    @use_timepicker
    def dispatch(self, *args, **kwargs):
        return super(CreateScheduleView, self).dispatch(*args, **kwargs)

    @property
    def parent_pages(self):
        return [
            {
                'title': BroadcastListView.page_title,
                'url': reverse(BroadcastListView.urlname, args=[self.domain]),
            },
        ]

    @property
    def broadcast(self):
        return None

    @property
    def schedule(self):
        return None

    @cached_property
    def schedule_form(self):
        args = [self.domain, self.schedule, self.can_use_inbound_sms, self.broadcast]

        if self.request.method == 'POST':
            args.append(self.request.POST)

        return BroadcastForm(*args, is_system_admin=self.is_system_admin)

    @property
    def page_context(self):
        context = super().page_context
        context.update({
            'schedule_form': self.schedule_form,
            'read_only_mode': self.read_only_mode,
        })
        return context

    def post(self, request, *args, **kwargs):
        if self.async_response is not None:
            return self.async_response

        if self.schedule_form.is_valid():
            if not self.can_use_inbound_sms and self.schedule_form.uses_sms_survey:
                return HttpResponseBadRequest(
                    "Cannot create or edit survey reminders because subscription "
                    "does not have access to inbound SMS"
                )

            broadcast, schedule = self.schedule_form.save_broadcast_and_schedule()
            if isinstance(schedule, AlertSchedule):
                refresh_alert_schedule_instances.delay(schedule.schedule_id.hex, broadcast.recipients)
            elif isinstance(schedule, TimedSchedule):
                refresh_timed_schedule_instances.delay(
                    schedule.schedule_id.hex,
                    broadcast.recipients,
                    start_date_iso_string=json_format_date(broadcast.start_date)
                )
            else:
                raise TypeError("Expected AlertSchedule or TimedSchedule")

            return HttpResponseRedirect(reverse(BroadcastListView.urlname, args=[self.domain]))

        return self.get(request, *args, **kwargs)


class EditScheduleView(CreateScheduleView):
    urlname = 'edit_schedule'
    page_title = gettext_lazy('Edit Broadcast')

    IMMEDIATE_BROADCAST = 'immediate'
    SCHEDULED_BROADCAST = 'scheduled'

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.broadcast_type, self.broadcast_id])

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
            return (
                self.broadcast_class
                .objects
                .prefetch_related('schedule')
                .get(pk=self.broadcast_id, domain=self.domain, deleted=False)
            )
        except self.broadcast_class.DoesNotExist:
            raise Http404()

    @property
    def schedule(self):
        return self.broadcast.schedule

    @cached_property
    def read_only_mode(self):
        immediate_broadcast_restriction = isinstance(self.broadcast, ImmediateBroadcast)

        inbound_sms_restriction = (
            not self.can_use_inbound_sms and
            self.schedule.memoized_uses_sms_survey
        )

        return immediate_broadcast_restriction or inbound_sms_restriction

    def dispatch(self, request, *args, **kwargs):
        with get_broadcast_edit_critical_section(self.broadcast_type, self.broadcast_id):
            if not self.can_use_inbound_sms and self.schedule.memoized_uses_sms_survey:
                messages.warning(
                    request,
                    _("This broadcast is not editable because it uses an SMS survey and "
                      "your current subscription does not allow use of inbound SMS.")
                )
            return super(EditScheduleView, self).dispatch(request, *args, **kwargs)


class ConditionalAlertBaseView(BaseMessagingSectionView):
    @method_decorator(requires_privilege_with_fallback(privileges.REMINDERS_FRAMEWORK))
    def dispatch(self, *args, **kwargs):
        return super(ConditionalAlertBaseView, self).dispatch(*args, **kwargs)

    def get_conditional_alerts_queryset(self, query_string=''):
        return get_conditional_alerts_queryset_by_domain(self.domain, query_string=query_string)


class ConditionalAlertListView(ConditionalAlertBaseView):
    """List conditional alerts for editing and monitoring processing status

    The "active" status displayed in the list is NOT the rule's active
    flag (`rule.active`); instead, it is the rule's schedule's active
    flag. Rule processing is triggered automatically when the rule is
    saved _if the *rule* is active_ (and there is no way to deactivate
    a conditional alert rule with the UI, only its schedule can be
    (de)activated). Therefore rule processing occurs unconditionally
    every time a rule is saved.

    The theory of operation is to create rules in the inactive state
    one-by-one while monitoring system performance. A rule can be
    activated once it has successfully processed all cases matching its
    case type. Rule activation triggers a rule processing run.

    TODO determine if rule processing run on (de)activate is necessary.
    """

    template_name = 'scheduling/conditional_alert_list.html'
    urlname = 'conditional_alert_list'
    refresh_urlname = 'conditional_alert_list_refresh'
    page_title = gettext_lazy('Conditional Alerts')

    LIST_CONDITIONAL_ALERTS = 'list_conditional_alerts'
    ACTION_ACTIVATE = 'activate'
    ACTION_DEACTIVATE = 'deactivate'
    ACTION_DELETE = 'delete'
    ACTION_RESTART = 'restart'

    @use_datatables
    def dispatch(self, *args, **kwargs):
        return super(ConditionalAlertListView, self).dispatch(*args, **kwargs)

    @cached_property
    def limit_rule_restarts(self):
        # If the user is a superuser, don't limit the number of times they
        # can restart a rule run. Also don't limit it if it's an environment
        # that is a standalone environment.
        return not (
            self.request.couch_user.is_superuser or
            settings.SERVER_ENVIRONMENT in settings.UNLIMITED_RULE_RESTART_ENVS
        )

    @property
    def page_context(self):
        context = super().page_context
        context['limit_rule_restarts'] = self.limit_rule_restarts
        return context

    def schedule_is_editable(self, schedule):
        return (
            (self.can_use_inbound_sms or not schedule.memoized_uses_sms_survey) and
            not schedule.memoized_uses_ivr_survey and
            not schedule.memoized_uses_sms_callback
        )

    def _format_rule_for_json(self, rule):
        schedule = rule.get_schedule()
        return {
            'name': rule.name,
            'case_type': rule.case_type,
            'active': schedule.active,
            'editable': self.schedule_is_editable(schedule),
            'locked_for_editing': rule.locked_for_editing,
            'progress_pct': MessagingRuleProgressHelper(rule.pk).get_progress_pct(),
            'id': rule.pk,
        }

    def get_conditional_alerts_ajax_response(self, request):
        query = self.get_conditional_alerts_queryset(query_string=request.GET.get('query', ''))
        total_records = query.count()

        limit = int(request.GET.get('limit'))
        page = int(request.GET.get('page', 1))
        skip = (page - 1) * limit

        rules = query[skip:skip + limit]
        data = [self._format_rule_for_json(rule) for rule in rules]

        return JsonResponse({
            'rules': data,
            'total': total_records,
        })

    def get(self, request, *args, **kwargs):
        action = request.GET.get('action')
        if action == self.LIST_CONDITIONAL_ALERTS:
            return self.get_conditional_alerts_ajax_response(request)

        return super(ConditionalAlertListView, self).get(*args, **kwargs)

    def get_rule(self, rule_id):
        try:
            return AutomaticUpdateRule.objects.get(
                domain=self.domain,
                pk=rule_id,
                deleted=False,
                workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING
            )
        except AutomaticUpdateRule.DoesNotExist:
            raise Http404()

    def get_activate_ajax_response(self, active_flag, rule):
        """
        When we deactivate a conditional alert from the UI, we are only
        deactivating the schedule that sends the content. The rule itself
        stays active.
        This is because we want to be keeping all the schedule instances
        up to date (though inactive), so that if the schedule is reactivated,
        we don't send a large quantity of stale messages.
        """
        with transaction.atomic():
            schedule = rule.get_schedule()
            if active_flag and not self.can_use_inbound_sms and schedule.memoized_uses_sms_survey:
                return HttpResponseBadRequest(
                    "Cannot create or edit survey reminders because subscription "
                    "does not have access to inbound SMS"
                )

            if active_flag and (rule.references_parent_case or schedule.references_parent_case):
                return HttpResponseBadRequest(
                    "Cannot reactivate alerts that reference parent case properties"
                )

            if active_flag and (schedule.memoized_uses_ivr_survey or schedule.memoized_uses_sms_callback):
                return HttpResponseBadRequest(
                    "Cannot activate alerts which use IVR or SMS Callback use cases since they "
                    "are no longer supported."
                )

            schedule.active = active_flag
            schedule.save()
            initiate_messaging_rule_run(rule)

        return JsonResponse({
            'status': 'success',
            'rule': self._format_rule_for_json(rule),
        })

    def get_delete_ajax_response(self, rule):
        rule.soft_delete()
        return JsonResponse({
            'status': 'success',
            'rule': self._format_rule_for_json(rule),
        })

    def get_restart_ajax_response(self, rule):
        helper = MessagingRuleProgressHelper(rule.pk)
        if self.limit_rule_restarts and helper.rule_initiation_key_is_set():
            minutes_remaining = helper.rule_initiation_key_minutes_remaining()
            return JsonResponse({'status': 'error', 'minutes_remaining': minutes_remaining})

        initiate_messaging_rule_run(rule)
        return JsonResponse({
            'status': 'success',
            'rule': self._format_rule_for_json(rule),
        })

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        rule_id = request.POST.get('rule_id')

        with get_conditional_alert_edit_critical_section(rule_id):
            rule = self.get_rule(rule_id)
            if rule.locked_for_editing and action != self.ACTION_RESTART:
                return HttpResponseBadRequest()

            if action == self.ACTION_ACTIVATE:
                return self.get_activate_ajax_response(True, rule)
            elif action == self.ACTION_DEACTIVATE:
                return self.get_activate_ajax_response(False, rule)
            elif action == self.ACTION_DELETE:
                return self.get_delete_ajax_response(rule)
            elif action == self.ACTION_RESTART:
                return self.get_restart_ajax_response(rule)
            else:
                return HttpResponseBadRequest()


class CreateConditionalAlertView(BaseMessagingSectionView, AsyncHandlerMixin):
    urlname = 'create_conditional_alert'
    page_title = gettext_lazy('New Conditional Alert')
    template_name = 'scheduling/conditional_alert.html'
    async_handlers = [ConditionalAlertAsyncHandler]
    read_only_mode = False

    @property
    def help_text(self):
        help_url = 'https://confluence.dimagi.com/display/commcarepublic/Conditional+Alerts'
        link = format_html('<a target="_blank" href="{}">{}</a>', help_url, _("Conditional Alerts"))
        return format_html(_('For information on Conditional Alerts, see the {} help page.'), link)

    @method_decorator(requires_privilege_with_fallback(privileges.REMINDERS_FRAMEWORK))
    @use_jquery_ui
    @use_timepicker
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
        context = super().page_context
        context.update({
            'all_case_properties': {
                t: sorted(names) for t, names in
                get_data_dict_props_by_case_type(self.domain).items()
            },
            'basic_info_form': self.basic_info_form,
            'criteria_form': self.criteria_form,
            'help_text': self.help_text,
            'schedule_form': self.schedule_form,
            'read_only_mode': self.read_only_mode,
            'is_system_admin': self.is_system_admin,
            'criteria_form_active': False,
            'schedule_form_active': False,
            'new_rule': not bool(self.rule),
            'rule_name': self.rule.name if self.rule else '',
        })

        if self.request.method == 'POST':
            context.update({
                'criteria_form_active': not self.criteria_form.is_valid() or self.schedule_form.is_valid(),
                'schedule_form_active': not self.schedule_form.is_valid() and self.criteria_form.is_valid(),
                'rule_name': self.basic_info_form.rule_name,
            })

        return context

    @cached_property
    def schedule_form(self):
        args = [
            self.domain,
            self.schedule,
            self.can_use_inbound_sms,
            self.rule,
            self.criteria_form,
        ]

        if self.request.method == 'POST':
            args.append(self.request.POST)

        return ConditionalAlertScheduleForm(
            *args,
            is_system_admin=self.is_system_admin
        )

    @property
    def schedule(self):
        return None

    @property
    def rule(self):
        return None

    @cached_property
    def basic_info_form(self):
        if self.request.method == 'POST':
            return ConditionalAlertForm(self.domain, self.rule, self.request.POST)

        return ConditionalAlertForm(self.domain, self.rule)

    @cached_property
    def criteria_form(self):
        kwargs = {
            'rule': self.rule,
            'is_system_admin': self.is_system_admin,
        }

        if self.request.method == 'POST':
            return ConditionalAlertCriteriaForm(self.domain, self.request.POST, **kwargs)

        return ConditionalAlertCriteriaForm(self.domain, **kwargs)

    def post(self, request, *args, **kwargs):
        if self.async_response is not None:
            return self.async_response

        basic_info_form_valid = self.basic_info_form.is_valid()
        criteria_form_valid = self.criteria_form.is_valid()
        schedule_form_valid = self.schedule_form.is_valid()

        if self.read_only_mode:
            # Don't allow making changes to rules that have custom
            # criteria/actions unless the user has permission to
            return HttpResponseBadRequest()

        if basic_info_form_valid and criteria_form_valid and schedule_form_valid:
            if not self.is_system_admin and (
                self.criteria_form.requires_system_admin_to_save or
                self.schedule_form.requires_system_admin_to_save
            ):
                # Don't allow adding custom criteria/actions to rules
                # unless the user has permission to
                return HttpResponseBadRequest()

            if not self.can_use_inbound_sms and self.schedule_form.uses_sms_survey:
                return HttpResponseBadRequest(
                    "Cannot create or edit survey reminders because subscription "
                    "does not have access to inbound SMS"
                )

            with transaction.atomic():
                if self.rule:
                    rule = self.rule
                else:
                    rule = AutomaticUpdateRule(
                        domain=self.domain,
                        active=True,
                        workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING,
                    )

                rule.name = self.basic_info_form.cleaned_data['name']
                self.criteria_form.save_criteria(rule)
                self.schedule_form.save_rule_action_and_schedule(rule)

            initiate_messaging_rule_run(rule)
            return HttpResponseRedirect(reverse(ConditionalAlertListView.urlname, args=[self.domain]))

        return self.get(request, *args, **kwargs)


class EditConditionalAlertView(CreateConditionalAlertView):
    urlname = 'edit_conditional_alert'
    page_title = gettext_lazy('Edit Conditional Alert')

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.rule_id])

    @property
    def help_text(self):
        return format_html('{}<br>{}',
            super().help_text,
            _("Editing a conditional alert will cause it to process each case of the alert's case type. "
              "This may take some time.")
        )

    @property
    def rule_id(self):
        return self.kwargs.get('rule_id')

    @cached_property
    def read_only_mode(self):
        system_admin_restriction = (
            not self.is_system_admin and
            (
                self.criteria_form.requires_system_admin_to_edit or
                self.schedule_form.requires_system_admin_to_edit
            )
        )

        inbound_sms_restriction = (
            not self.can_use_inbound_sms and
            self.schedule.memoized_uses_sms_survey
        )

        return (
            system_admin_restriction or
            inbound_sms_restriction or
            self.schedule.memoized_uses_ivr_survey or
            self.schedule.memoized_uses_sms_callback
        )

    @cached_property
    def rule(self):
        try:
            return AutomaticUpdateRule.objects.get(
                pk=self.rule_id,
                domain=self.domain,
                workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING,
                deleted=False,
            )
        except AutomaticUpdateRule.DoesNotExist:
            raise Http404()

    @cached_property
    def schedule(self):
        return self.rule.get_schedule()

    def dispatch(self, request, *args, **kwargs):
        with get_conditional_alert_edit_critical_section(self.rule_id):
            if self.rule.locked_for_editing:
                messages.warning(request, _("Please allow the rule to finish processing before editing."))
                return HttpResponseRedirect(reverse(ConditionalAlertListView.urlname, args=[self.domain]))
            if not self.can_use_inbound_sms and self.schedule.memoized_uses_sms_survey:
                messages.warning(
                    request,
                    _("This alert is not editable because it uses an SMS survey and "
                      "your current subscription does not allow use of inbound SMS.")
                )
            if self.schedule.memoized_uses_ivr_survey:
                messages.warning(
                    request,
                    _("This alert is not editable because it uses IVR, which is no longer supported.")
                )
            if self.schedule.memoized_uses_sms_callback:
                messages.warning(
                    request,
                    _("This alert is not editable because it uses the SMS / Callback workflow, "
                      "which is no longer supported.")
                )
            if self.rule.references_parent_case or self.schedule.references_parent_case:
                """
                There are no active reminders which reference parent case properties anymore.
                Keeping reminder rules that have parent case references up-to-date with case
                changes is tough on performance because you have to run the rules against
                all applicable subcases when a parent case changes, so while the framework does
                use .resolve_case_property() to handle these lookups properly, it no longer runs
                the rules against all subcases when a parent case changes, and therefore doesn't
                support this use case.

                The form validation doesn't allow creating parent case references so trying
                to save will cause validation to fail, but in case one of the older, inactive,
                reminders is being edited we display this warning.
                """
                messages.warning(
                    request,
                    _("This conditional alert references parent case properties. Note that changes "
                      "to parent cases will not be immediately reflected by the alert and will "
                      "only be reflected once the child case is subsequently updated. For best "
                      "results, please update your workflow to avoid referencing parent case "
                      "properties in this alert.")
                )
            return super(EditConditionalAlertView, self).dispatch(request, *args, **kwargs)


class DownloadConditionalAlertView(ConditionalAlertBaseView):
    urlname = 'download_conditional_alert'
    http_method_names = ['get']

    def dispatch(self, *args, **kwargs):
        return super(DownloadConditionalAlertView, self).dispatch(*args, **kwargs)

    def get(self, request, domain):
        headers = get_conditional_alert_headers(self.domain)
        (translated_rows, untranslated_rows) = get_conditional_alert_rows(self.domain)

        temp = io.BytesIO()
        export_raw(
            headers, [
                (TranslatedConditionalAlertUploader.sheet_name, translated_rows),
                (UntranslatedConditionalAlertUploader.sheet_name, untranslated_rows),
            ], temp)
        filename = 'Conditional Alerts - {domain}'.format(domain=domain)
        return export_response(temp, Format.XLS_2007, filename)


class UploadConditionalAlertView(BaseMessagingSectionView):
    urlname = 'upload_conditional_alert'
    page_title = gettext_lazy("Upload SMS Alert Content")
    template_name = 'hqwebapp/bulk_upload.html'

    @method_decorator(requires_privilege_with_fallback(privileges.REMINDERS_FRAMEWORK))
    def dispatch(self, *args, **kwargs):
        return super(UploadConditionalAlertView, self).dispatch(*args, **kwargs)

    @property
    def page_context(self):
        context = super().page_context
        context.update({
            'bulk_upload': {
                "download_url": reverse("download_conditional_alert", args=(self.domain,)),
                "adjective": _("SMS alert content"),
                "plural_noun": _("SMS alert content"),
                "help_link": "https://confluence.dimagi.com/display/commcarepublic/Bulk+download+and+upload+of+SMS+content+in+conditional+alerts", # noqa
            },
        })
        context.update({
            'bulk_upload_form': get_bulk_upload_form(context),
        })
        return context

    @property
    def parent_pages(self):
        return [{
            'title': BroadcastListView.page_title,
            'url': reverse(BroadcastListView.urlname, args=[self.domain]),
        }]

    def post(self, request, *args, **kwargs):
        try:
            workbook = get_workbook(request.FILES['bulk_upload_file'])
        except WorkbookJSONError as e:
            messages.error(request, str(e))
            return self.get(request, *args, **kwargs)

        msgs = upload_conditional_alert_workbook(self.domain, workbook)
        for msg in msgs:
            msg[0](request, msg[1])

        return self.get(request, *args, **kwargs)


@requires_privilege_json_response(privileges.REMINDERS_FRAMEWORK)
@require_permission(HqPermissions.edit_messaging)
@RICH_TEXT_EMAILS.required_decorator()
def messaging_image_upload_view(request, domain):
    if request.method == 'POST' and request.FILES.get('upload'):
        image_file = request.FILES['upload']

        if image_file.size > MAX_IMAGE_UPLOAD_SIZE:
            return JsonResponse({
                'error': {
                    "message": _('Image file is too large. Images must be smaller than 1MB'),
                }
            }, status=400)

        if image_file.content_type not in VALID_EMAIL_IMAGE_MIMETYPES:
            image_extensions = [mimetype.split("/")[1] for mimetype in VALID_EMAIL_IMAGE_MIMETYPES]
            return JsonResponse({
                'error': {
                    "message": _('You can only upload {image_extensions} images').format(
                        image_extensions=", ".join(image_extensions))
                },
            }, status=400)

        image = EmailImage.save_blob(
            image_file,
            domain=request.domain,
            filename=image_file.name,
            content_type=image_file.content_type,
        )
        return JsonResponse({
            'url': absolute_reverse("download_messaging_image", args=[domain, image.blob_id])
        }, status=201)
    return JsonResponse({'error': {"message": _('Invalid request')}}, status=400)


def messaging_image_download_view(request, domain, image_key):
    """This view is intentionally left unauthenticated, as it returns images
    that are sent in rich-text email messages.

    """
    try:
        image_meta = EmailImage.get_by_key(domain, image_key)
        image_blob = image_meta.get_blob()
    except (EmailImage.DoesNotExist, NotFound):
        # We could instead serve a placeholder image here
        raise Http404()

    return HttpResponse(image_blob, content_type=image_meta.content_type)
