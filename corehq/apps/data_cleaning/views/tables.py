from django.utils.decorators import method_decorator

from corehq import toggles
from corehq.apps.data_cleaning.tables import (
    CleanCaseTable,
    CaseCleaningTasksTable,
)
from corehq.apps.domain.decorators import LoginAndDomainMixin
from corehq.apps.domain.views import DomainViewMixin
from corehq.apps.es import CaseSearchES
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.hqwebapp.tables.pagination import SelectablePaginatedTableView


@method_decorator([
    use_bootstrap5,
    toggles.DATA_CLEANING_CASES.required_decorator(),
], name='dispatch')
class BaseDataCleaningTableView(LoginAndDomainMixin, DomainViewMixin, SelectablePaginatedTableView):
    pass


class CleanCasesTableView(BaseDataCleaningTableView):
    urlname = "data_cleaning_cases_table"
    table_class = CleanCaseTable

    @property
    def session_id(self):
        return self.kwargs['session_id']

    def get_queryset(self):
        return CaseSearchES().domain(self.domain)


class CaseCleaningTasksTableView(BaseDataCleaningTableView):
    urlname = "case_data_cleaning_tasks_table"
    table_class = CaseCleaningTasksTable

    def get_queryset(self):
        return [
            {
                "status": "test",
                "time": "no time",
                "case_type": "placeholder",
                "details": "foo",
            }
        ]
