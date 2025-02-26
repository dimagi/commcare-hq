from memoized import memoized

from django.http import Http404
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _

from corehq import toggles
from corehq.apps.data_cleaning.models import BulkEditSession
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
    @memoized
    def session(self):
        try:
            return BulkEditSession.objects.get(session_id=self.session_id)
        except BulkEditSession.DoesNotExist:
            raise Http404(_("Data cleaning session was not found."))

    @property
    def case_type(self):
        return self.session.identifier

    @property
    def session_id(self):
        return self.kwargs['session_id']

    def get_table_kwargs(self):
        return {
            'extra_columns': self.table_class.get_columns_from_session(self.session),
        }

    def get_queryset(self):
        return CaseSearchES().domain(self.domain).case_type(self.case_type)


class CaseCleaningTasksTableView(BaseDataCleaningTableView):
    urlname = "case_data_cleaning_tasks_table"
    table_class = CaseCleaningTasksTable

    def get_queryset(self):
        return [{
            "status": session.status,
            "committed_on": session.committed_on,
            "completed_on": session.completed_on,
            "case_type": session.identifier,
            "details": session.result,
        } for session in BulkEditSession.get_committed_sessions(self.request.user, self.domain)]
