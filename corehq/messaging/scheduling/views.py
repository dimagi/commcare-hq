from __future__ import absolute_import
from __future__ import unicode_literals
from functools import wraps
from django.contrib import messages
from django.db import transaction
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseRedirect,
    HttpResponseBadRequest,
)
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import ugettext as _, ugettext_lazy

from corehq import privileges
from corehq import toggles
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.data_interfaces.models import AutomaticUpdateRule, CreateScheduleInstanceActionDefinition
from corehq.apps.domain.models import Domain
from corehq.apps.sms.views import BaseMessagingSectionView
from corehq.apps.hqwebapp.async_handler import AsyncHandlerMixin
from corehq.apps.hqwebapp.decorators import use_datatables, use_select2, use_jquery_ui, use_timepicker
from corehq.apps.hqwebapp.views import DataTablesAJAXPaginationMixin
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from corehq.messaging.scheduling.async_handlers import MessagingRecipientHandler, ConditionalAlertAsyncHandler
from corehq.messaging.scheduling.forms import (
    BroadcastForm,
    ConditionalAlertForm,
    ConditionalAlertCriteriaForm,
    ConditionalAlertScheduleForm,
)
from corehq.messaging.scheduling.models import (
    AlertSchedule,
    TimedSchedule,
    ImmediateBroadcast,
    ScheduledBroadcast,
)
from corehq.messaging.scheduling.tasks import refresh_alert_schedule_instances, refresh_timed_schedule_instances
from corehq.messaging.tasks import initiate_messaging_rule_run
from corehq.messaging.util import MessagingRuleProgressHelper
from corehq.const import SERVER_DATETIME_FORMAT
from corehq.util.timezones.conversions import ServerTime
from corehq.util.timezones.utils import get_timezone_for_user
from dimagi.utils.couch import CriticalSection


def get_broadcast_edit_critical_section(broadcast_type, broadcast_id):
    return CriticalSection(['edit-broadcast-%s-%s' % (broadcast_type, broadcast_id)], timeout=5 * 60)


def get_conditional_alert_edit_critical_section(rule_id):
    return CriticalSection(['edit-conditional-alert-%s' % rule_id], timeout=5 * 60)


def _requires_new_reminder_framework():
    def decorate(fn):
        @wraps(fn)
        def wrapped(request, *args, **kwargs):
            if (
                hasattr(request, 'couch_user') and
                toggles.NEW_REMINDERS_MIGRATOR.enabled(request.couch_user.username)
            ):
                return fn(request, *args, **kwargs)
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
    page_title = ugettext_lazy('Schedule a Message')

    LIST_SCHEDULED = 'list_scheduled'
    LIST_IMMEDIATE = 'list_immediate'
    ACTION_ACTIVATE_SCHEDULED_BROADCAST = 'activate_scheduled_broadcast'
    ACTION_DEACTIVATE_SCHEDULED_BROADCAST = 'deactivate_scheduled_broadcast'
    ACTION_DELETE_SCHEDULED_BROADCAST = 'delete_scheduled_broadcast'

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
            .filter(domain=self.domain, deleted=False)
            .order_by('-last_sent_timestamp', 'id')
        )
        total_records = query.count()
        query = query.select_related('schedule')
        broadcasts = query[self.display_start:self.display_start + self.display_length]

        data = []
        for broadcast in broadcasts:
            data.append({
                'name': broadcast.name,
                'last_sent': self._format_time(broadcast.last_sent_timestamp),
                'active': broadcast.schedule.active,
                'editable': self.can_use_inbound_sms or not broadcast.schedule.memoized_uses_sms_survey,
                'id': broadcast.id,
            })
        return self.datatables_ajax_response(data, total_records)

    def get_immediate_ajax_response(self):
        query = (
            ImmediateBroadcast.objects
            .filter(domain=self.domain, deleted=False)
            .order_by('-last_sent_timestamp', 'id')
        )
        total_records = query.count()
        broadcasts = query[self.display_start:self.display_start + self.display_length]

        data = []
        for broadcast in broadcasts:
            data.append({
                'name': broadcast.name,
                'last_sent': self._format_time(broadcast.last_sent_timestamp),
                'id': broadcast.id,
            })
        return self.datatables_ajax_response(data, total_records)

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
            broadcast.schedule_id,
            broadcast.recipients,
            start_date=broadcast.start_date
        )

        return HttpResponse()

    def get_scheduled_broadcast_delete_ajax_response(self, broadcast_id):
        broadcast = self.get_scheduled_broadcast(broadcast_id)
        broadcast.soft_delete()
        return HttpResponse()

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
    page_title = ugettext_lazy('Schedule a Message')
    template_name = 'scheduling/create_schedule.html'
    async_handlers = [MessagingRecipientHandler]
    read_only_mode = False

    @method_decorator(_requires_new_reminder_framework())
    @method_decorator(requires_privilege_with_fallback(privileges.OUTBOUND_SMS))
    @method_decorator(require_permission(Permissions.edit_data))
    @use_jquery_ui
    @use_timepicker
    @use_select2
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

        return BroadcastForm(*args)

    @property
    def page_context(self):
        return {
            'schedule_form': self.schedule_form,
            'read_only_mode': self.read_only_mode,
        }

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
                refresh_alert_schedule_instances.delay(schedule.schedule_id, broadcast.recipients)
            elif isinstance(schedule, TimedSchedule):
                refresh_timed_schedule_instances.delay(schedule.schedule_id, broadcast.recipients,
                    start_date=broadcast.start_date)
            else:
                raise TypeError("Expected AlertSchedule or TimedSchedule")

            return HttpResponseRedirect(reverse(BroadcastListView.urlname, args=[self.domain]))

        return self.get(request, *args, **kwargs)


class EditScheduleView(CreateScheduleView):
    urlname = 'edit_schedule'
    page_title = ugettext_lazy('Edit Scheduled Message')

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


class ConditionalAlertListView(BaseMessagingSectionView, DataTablesAJAXPaginationMixin):
    template_name = 'scheduling/conditional_alert_list.html'
    urlname = 'conditional_alert_list'
    page_title = ugettext_lazy('Schedule a Conditional Message')

    LIST_CONDITIONAL_ALERTS = 'list_conditional_alerts'
    ACTION_ACTIVATE = 'activate'
    ACTION_DEACTIVATE = 'deactivate'
    ACTION_DELETE = 'delete'

    @method_decorator(_requires_new_reminder_framework())
    @method_decorator(requires_privilege_with_fallback(privileges.OUTBOUND_SMS))
    @method_decorator(require_permission(Permissions.edit_data))
    @use_datatables
    def dispatch(self, *args, **kwargs):
        return super(ConditionalAlertListView, self).dispatch(*args, **kwargs)

    def get_conditional_alerts_queryset(self):
        return (
            AutomaticUpdateRule
            .objects
            .filter(domain=self.domain, workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING, deleted=False)
            .order_by('case_type', 'name', 'id')
        )

    def get_conditional_alerts_ajax_response(self):
        query = self.get_conditional_alerts_queryset()
        total_records = query.count()

        rules = query[self.display_start:self.display_start + self.display_length]
        data = []
        for rule in rules:
            schedule = rule.get_messaging_rule_schedule()
            data.append({
                'name': rule.name,
                'case_type': rule.case_type,
                'active': schedule.active,
                'editable': self.can_use_inbound_sms or not schedule.memoized_uses_sms_survey,
                'locked_for_editing': rule.locked_for_editing,
                'progress_pct': MessagingRuleProgressHelper(rule.pk).get_progress_pct(),
                'id': rule.pk,
            })

        return self.datatables_ajax_response(data, total_records)

    def get(self, request, *args, **kwargs):
        action = request.GET.get('action')
        if action == self.LIST_CONDITIONAL_ALERTS:
            return self.get_conditional_alerts_ajax_response()

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
            schedule = rule.get_messaging_rule_schedule()
            if not self.can_use_inbound_sms and schedule.memoized_uses_sms_survey:
                return HttpResponseBadRequest(
                    "Cannot create or edit survey reminders because subscription "
                    "does not have access to inbound SMS"
                )

            schedule.active = active_flag
            schedule.save()
            initiate_messaging_rule_run(self.domain, rule.pk)

        return HttpResponse()

    def get_delete_ajax_response(self, rule):
        rule.soft_delete()
        return HttpResponse()

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        rule_id = request.POST.get('rule_id')

        with get_conditional_alert_edit_critical_section(rule_id):
            rule = self.get_rule(rule_id)
            if rule.locked_for_editing:
                return HttpResponseBadRequest()

            if action == self.ACTION_ACTIVATE:
                return self.get_activate_ajax_response(True, rule)
            elif action == self.ACTION_DEACTIVATE:
                return self.get_activate_ajax_response(False, rule)
            elif action == self.ACTION_DELETE:
                return self.get_delete_ajax_response(rule)
            else:
                return HttpResponseBadRequest()


class CreateConditionalAlertView(BaseMessagingSectionView, AsyncHandlerMixin):
    urlname = 'create_conditional_alert'
    page_title = ugettext_lazy('New Conditional Message')
    template_name = 'scheduling/conditional_alert.html'
    async_handlers = [ConditionalAlertAsyncHandler]
    read_only_mode = False

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
            'schedule_form': self.schedule_form,
            'read_only_mode': self.read_only_mode,
            'criteria_form_active': self.criteria_form.errors or not self.schedule_form.errors,
            'schedule_form_active': self.schedule_form.errors and not self.criteria_form.errors,
        }

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

        return ConditionalAlertScheduleForm(*args)

    @property
    def schedule(self):
        return None

    @property
    def rule(self):
        return None

    @cached_property
    def is_system_admin(self):
        return self.request.couch_user.is_superuser

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
                        migrated=True,
                        workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING,
                    )

                rule.name = self.basic_info_form.cleaned_data['name']
                self.criteria_form.save_criteria(rule)
                self.schedule_form.save_rule_action_and_schedule(rule)

            initiate_messaging_rule_run(rule.domain, rule.pk)
            return HttpResponseRedirect(reverse(ConditionalAlertListView.urlname, args=[self.domain]))

        return self.get(request, *args, **kwargs)


class EditConditionalAlertView(CreateConditionalAlertView):
    urlname = 'edit_conditional_alert'
    page_title = ugettext_lazy('Edit Conditional Message')

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.rule_id])

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

        return system_admin_restriction or inbound_sms_restriction

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
        return self.rule.get_messaging_rule_schedule()

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
            return super(EditConditionalAlertView, self).dispatch(request, *args, **kwargs)
