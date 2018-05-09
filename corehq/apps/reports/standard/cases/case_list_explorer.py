from __future__ import absolute_import, unicode_literals

from django.utils.translation import ugettext_lazy

from corehq.apps.reports.standard.cases.basic import CaseListReport
from corehq.apps.es import CaseSearchES


class CaseListExplorer(CaseListReport):
    name = ugettext_lazy('Case List Explorer')
    slug = 'case_list_explorer'
    search_class = CaseSearchES

    fields = [
        'corehq.apps.reports.filters.case_list.CaseListFilter',
        'corehq.apps.reports.filters.select.CaseTypeFilter',
        'corehq.apps.reports.filters.select.SelectOpenCloseFilter',
        'corehq.apps.reports.standard.cases.filters.XpathCaseSearchFilter',
    ]

    def _build_query(self):
        query = super(CaseListExplorer, self)._build_query()
        xpath = self.request.GET.get('search_xpath')
        if xpath:
            query = query.xpath_query(self.domain, xpath)
        return query
