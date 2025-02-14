from django.utils.decorators import method_decorator

from corehq import toggles
from corehq.apps.data_cleaning.tables import CleanCaseTable
from corehq.apps.domain.decorators import LoginAndDomainMixin
from corehq.apps.domain.views import BaseDomainView, DomainViewMixin
from corehq.apps.es import CaseSearchES
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.hqwebapp.tables.pagination import SelectablePaginatedTableView


@method_decorator([
    use_bootstrap5,
    toggles.DATA_CLEANING_CASES.required_decorator(),
], name='dispatch')
class CleanCasesMainView(BaseDomainView):
    urlname = "data_cleaning_cases"
    template_name = "data_cleaning/cases.html"

    @property
    def section_url(self):
        return ""


@method_decorator(toggles.DATA_CLEANING_CASES.required_decorator(), name='dispatch')
class CleanCasesTableView(LoginAndDomainMixin, DomainViewMixin, SelectablePaginatedTableView):
    urlname = "data_cleaning_cases_table"
    table_class = CleanCaseTable

    def get_queryset(self):
        return CaseSearchES().domain(self.domain)
