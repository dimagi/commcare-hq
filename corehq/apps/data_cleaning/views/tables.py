from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe

from corehq import toggles
from corehq.apps.data_cleaning.models import BulkEditSession
from corehq.apps.data_cleaning.tables import (
    CleanCaseTable,
    CaseCleaningTasksTable,
)
from corehq.apps.data_cleaning.views.mixins import BulkEditSessionViewMixin
from corehq.apps.domain.decorators import LoginAndDomainMixin
from corehq.apps.domain.views import DomainViewMixin
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.hqwebapp.tables.pagination import SelectablePaginatedTableView


@method_decorator([
    use_bootstrap5,
    toggles.DATA_CLEANING_CASES.required_decorator(),
], name='dispatch')
class BaseDataCleaningTableView(LoginAndDomainMixin, DomainViewMixin, SelectablePaginatedTableView):
    pass


class CleanCasesTableView(BulkEditSessionViewMixin, BaseDataCleaningTableView):
    urlname = "data_cleaning_cases_table"
    table_class = CleanCaseTable

    def get_table_kwargs(self):
        return {
            'extra_columns': self.table_class.get_columns_from_session(self.session),
            'record_kwargs': {
                'session': self.session,
            },
        }

    def get_queryset(self):
        return self.session.get_queryset()


class CaseCleaningTasksTableView(BaseDataCleaningTableView):
    urlname = "case_data_cleaning_tasks_table"
    table_class = CaseCleaningTasksTable

    def get_queryset(self):
        return [{
            "status": mark_safe(self._get_status_content(session)),     # nosec: doesn't include user input
            "committed_on": session.committed_on,
            "completed_on": session.completed_on,
            "case_type": session.identifier,
            "details": session.result,
        } for session in BulkEditSession.get_committed_sessions(self.request.user, self.domain)]

    def _get_status_content(self, session):
        (status, status_class) = session.status_tuple
        return f"<span class='badge text-bg-{status_class}'>{status}</span>"
