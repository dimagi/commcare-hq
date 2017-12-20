from __future__ import absolute_import
from functools import wraps

from django.db import transaction
from django.http import (
    Http404,
    HttpResponseRedirect,
    HttpResponseBadRequest,
)
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

from corehq import privileges
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.data_interfaces.models import AutomaticUpdateRule, CreateScheduleInstanceActionDefinition
from corehq.apps.domain.models import Domain
from corehq.apps.sms.views import BaseMessagingSectionView
from corehq.apps.hqwebapp.async_handler import AsyncHandlerMixin
from corehq.apps.hqwebapp.decorators import use_datatables, use_select2, use_jquery_ui, use_timepicker
from corehq.apps.hqwebapp.views import DataTablesAJAXPaginationMixin
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from corehq.messaging.scheduling.async_handlers import MessagingRecipientHandler
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
            .order_by('-last_sent_timestamp', 'id')
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
            .order_by('-last_sent_timestamp', 'id')
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
        if self.request.method == 'POST':
            return BroadcastForm(self.domain, self.schedule, self.broadcast, self.request.POST)

        return BroadcastForm(self.domain, self.schedule, self.broadcast)

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
    page_title = _('Edit Scheduled Message')

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
            broadcast = self.broadcast_class.objects.prefetch_related('schedule').get(pk=self.broadcast_id)
        except self.broadcast_class.DoesNotExist:
            raise Http404()

        if broadcast.domain != self.domain:
            raise Http404()

        return broadcast

    @property
    def read_only_mode(self):
        return isinstance(self.broadcast, ImmediateBroadcast)

    @property
    def schedule(self):
        return self.broadcast.schedule


class ConditionalAlertListView(BaseMessagingSectionView, DataTablesAJAXPaginationMixin):
    template_name = 'scheduling/conditional_alert_list.html'
    urlname = 'conditional_alert_list'
    page_title = _('Schedule a Conditional Message')

    LIST_CONDITIONAL_ALERTS = 'list_conditional_alerts'

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
            .filter(domain=self.domain, workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING)
            .order_by('case_type', 'name', 'id')
        )

    def get_conditional_alerts_ajax_response(self):
        query = self.get_conditional_alerts_queryset()
        total_records = query.count()

        rules = query[self.display_start:self.display_start + self.display_length]
        data = []
        for rule in rules:
            data.append([
                '< delete placeholder >',
                rule.name,
                rule.case_type,
                rule.active,
                '< action placeholder >',
                rule.pk,
            ])

        return self.datatables_ajax_response(data, total_records)

    def get(self, request, *args, **kwargs):
        action = request.GET.get('action')
        if action == self.LIST_CONDITIONAL_ALERTS:
            return self.get_conditional_alerts_ajax_response()

        return super(ConditionalAlertListView, self).get(*args, **kwargs)


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
            'schedule_form': self.schedule_form,
            'read_only_mode': self.read_only_mode,
            'criteria_form_active': self.criteria_form.errors or not self.schedule_form.errors,
            'schedule_form_active': self.schedule_form.errors and not self.criteria_form.errors,
        }

    @cached_property
    def schedule_form(self):
        if self.request.method == 'POST':
            return ConditionalAlertScheduleForm(self.domain, self.schedule, self.rule, self.criteria_form,
                self.request.POST)

        return ConditionalAlertScheduleForm(self.domain, self.schedule, self.rule, self.criteria_form)

    @property
    def schedule(self):
        return None

    @property
    def rule(self):
        return None

    @cached_property
    def read_only_mode(self):
        return (
            not self.is_system_admin and
            (
                self.criteria_form.requires_system_admin_to_edit or
                self.schedule_form.requires_system_admin_to_edit
            )
        )

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
    page_title = _('Edit Conditional Message')

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.rule_id])

    @property
    def rule_id(self):
        return self.kwargs.get('rule_id')

    @cached_property
    def rule(self):
        try:
            return AutomaticUpdateRule.objects.get(
                pk=self.rule_id,
                domain=self.domain,
                workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING,
            )
        except AutomaticUpdateRule.DoesNotExist:
            raise Http404()

    @cached_property
    def schedule(self):
        if len(self.rule.memoized_actions) != 1:
            raise ValueError("Expected exactly 1 action")

        action = self.rule.memoized_actions[0]
        action_definition = action.definition
        if not isinstance(action_definition, CreateScheduleInstanceActionDefinition):
            raise TypeError("Expected CreateScheduleInstanceActionDefinition")

        return action_definition.schedule
