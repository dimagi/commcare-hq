from django.urls import reverse
from django.utils.decorators import method_decorator
from corehq.apps.data_cleaning.decorators import require_bulk_data_cleaning_cases
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
    require_bulk_data_cleaning_cases,
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
        return [
            self._get_record(session)
            for session in BulkEditSession.get_committed_sessions(self.request.user, self.domain)
        ]

    def _get_record(self, session):
        return {
            "committed_on": session.committed_on,
            "completed_on": session.completed_on,
            "case_type": session.identifier,
            "case_count": session.records.count(),
            "percent": session.percent_complete,
            "form_ids_url": reverse('download_form_ids', args=(session.domain, session.session_id)),
            "has_form_ids": bool(len(session.form_ids)),
        }
