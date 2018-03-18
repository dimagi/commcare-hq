from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.reports.filters.base import BaseReportFilter
from django.utils.translation import ugettext_lazy


class MessageConfigurationFilter(BaseReportFilter):
    label = ugettext_lazy("Messaging Configuration")
    slug = 'messaging_configuration_filter'
    template = 'scheduling/configuration_filter.html'

    TYPE_BROADCAST = 'broadcast'
    TYPE_CONDITIONAL_ALERT = 'conditional_alert'

    @property
    def filter_context(self):
        return {
            "initial_value": self.get_value(self.request, self.domain),
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
            'configuration_type': request.GET.get('configuration_type'),
            'rule_id': request.GET.get('rule_id'),
        }
