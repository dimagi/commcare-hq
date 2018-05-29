from __future__ import absolute_import, unicode_literals

from django.utils.translation import ugettext_lazy as _

from corehq.apps.es.case_search import CaseSearchES
from corehq.apps.reports.standard.cases.basic import CaseListReport
from corehq.apps.reports.standard.cases.filters import (
    XpathCaseSearchFilter,
)


class CaseListExplorer(CaseListReport):
    name = _('Case List Explorer')
    slug = 'case_list_explorer'
    search_class = CaseSearchES

    fields = [
        'corehq.apps.reports.filters.case_list.CaseListFilter',
        'corehq.apps.reports.filters.select.CaseTypeFilter',
        'corehq.apps.reports.filters.select.SelectOpenCloseFilter',
        XpathCaseSearchFilter,
    ]

    def get_data(self):
        for row in self.es_results['hits'].get('hits', []):
            yield flatten_result(row)

    def _build_query(self):
        query = super(CaseListExplorer, self)._build_query()
        xpath = XpathCaseSearchFilter.get_value(self.request, self.domain)
        if xpath:
            query = query.xpath_query(self.domain, xpath)
        return query

