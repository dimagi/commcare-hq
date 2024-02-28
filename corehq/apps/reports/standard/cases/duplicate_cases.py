from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext
from django.utils.html import format_html
from django.urls import reverse

from corehq.apps.reports.exceptions import BadRequestError
from corehq.apps.reports.standard.cases.case_list_explorer import (
    CaseListExplorer,
)
from corehq.apps.reports.standard.cases.filters import (
    CaseListExplorerColumns,
    DuplicateCaseRuleFilter,
    XPathCaseSearchFilter,
)
from corehq.apps.reports.filters.case_list import CaseListFilter
from corehq.apps.data_interfaces.models import CaseDuplicateNew


class DuplicateCasesExplorer(CaseListExplorer):
    name = _("Duplicate Cases")
    slug = 'duplicate_cases'

    fields = [
        DuplicateCaseRuleFilter,
        XPathCaseSearchFilter,
        CaseListExplorerColumns,
        CaseListFilter,
    ]

    def _get_case_ids(self):
        case_rule_id = DuplicateCaseRuleFilter.get_value(self.request, self.domain)
        if not case_rule_id:
            from corehq.apps.data_interfaces.views import DeduplicationRuleListView
            message = format_html(
                gettext(
                    'Please select a duplicate case rule to filter by above. If one does not exist, you may '
                    ' <a href={} target="_blank">create a new rule</a>'
                ),
                reverse(DeduplicationRuleListView.urlname, args=[self.domain])
            )

            raise BadRequestError(message)
        return CaseDuplicateNew.get_case_ids(case_rule_id)

    def _build_query(self, sort=True):
        query = super()._build_query(sort)
        query = query.case_ids(self._get_case_ids())
        return query

    def get_tracked_search_properties(self):
        from corehq.apps.accounting.models import Subscription, SubscriptionType
        properties = super().get_tracked_search_properties()

        subscription = Subscription.get_active_subscription_by_domain(self.domain)
        managed_by_saas = bool(subscription and subscription.service_type == SubscriptionType.PRODUCT)
        properties['managed_by_saas'] = managed_by_saas

        return properties
