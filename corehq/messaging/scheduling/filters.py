from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.reports.filters.base import BaseReportFilter
from django.utils.translation import ugettext_lazy


class ScheduleInstanceFilter(BaseReportFilter):
    label = ""
    slug = 'schedule_instance_filter'
    template = 'scheduling/schedule_instance_filter.html'

    TYPE_BROADCAST = 'broadcast'
    TYPE_CONDITIONAL_ALERT = 'conditional_alert'

    SHOW_ALL_EVENTS = 'all'
    SHOW_EVENTS_AFTER_DATE = 'only_after'

    @property
    def filter_context(self):
        return {
            'timezone': self.timezone.zone,
            'initial_value': self.get_value(self.request, self.domain),
            'conditional_alert_choices': self.get_conditional_alert_choices(),
        }

    def get_conditional_alert_choices(self):
        return list(AutomaticUpdateRule.objects.filter(
            domain=self.domain,
            deleted=False,
            workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING,
        ).values('id', 'name'))

    @classmethod
    def get_value(cls, request, domain):
        return {
            'date_selector_type': request.GET.get('date_selector_type'),
            'next_event_due_after': request.GET.get('next_event_due_after'),
            'configuration_type': request.GET.get('configuration_type'),
            'rule_id': request.GET.get('rule_id'),
            'active': request.GET.get('active'),
            'case_id': request.GET.get('case_id'),
        }
