from django.utils.translation import ugettext_lazy as _
from corehq.apps.reports.exceptions import BadRequestError
from corehq.apps.reports.standard.cases.case_list_explorer import (
    CaseListExplorer,
)
from corehq.apps.reports.standard.cases.filters import (
    CaseListExplorerColumns,
    DuplicateCaseRuleFilter,
    XpathCaseSearchFilter,
)
from corehq.apps.reports.filters.case_list import CaseListFilter
from corehq.apps.data_interfaces.models import CaseDuplicate


class DuplicateCasesExplorer(CaseListExplorer):
    name = _("Duplicate Cases")
    slug = 'duplicate_cases'

    fields = [
        DuplicateCaseRuleFilter,
        XpathCaseSearchFilter,
        CaseListExplorerColumns,
        CaseListFilter,
    ]

    def _get_case_ids(self):
        case_rule_id = DuplicateCaseRuleFilter.get_value(self.request, self.domain)
        if not case_rule_id:
            raise BadRequestError(_("Please select a duplicate case rule to filter by above."))
        return CaseDuplicate.get_case_ids(case_rule_id)

    def _build_query(self, sort=True):
        query = super()._build_query(sort)
        query = query.case_ids(self._get_case_ids())
        return query
