import json

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
from corehq.util.htmx_action import HqHtmxActionMixin, hq_hx_action


@method_decorator([
    use_bootstrap5,
    require_bulk_data_cleaning_cases,
], name='dispatch')
class BaseDataCleaningTableView(LoginAndDomainMixin, DomainViewMixin, SelectablePaginatedTableView):
    pass


class CleanCasesTableView(BulkEditSessionViewMixin, HqHtmxActionMixin, BaseDataCleaningTableView):
    urlname = "data_cleaning_cases_table"
    table_class = CleanCaseTable

    def get_table_kwargs(self):
        extra_columns = [(
            "selection",
            self.table_class.get_select_column(
                self.session,
                self.request,
                select_record_action="select_record",
                select_page_action="select_page",
            )
        )]
        extra_columns.extend(self.table_class.get_columns_from_session(self.session))
        return {
            'extra_columns': extra_columns,
            'record_kwargs': {
                'session': self.session,
            },
            'session': self.session,
        }

    def get_queryset(self):
        return self.session.get_queryset()

    @hq_hx_action('post')
    def clear_filters(self, request, *args, **kwargs):
        self.session.reset_filtering()
        response = self.get(request, *args, **kwargs)
        response['HX-Trigger'] = json.dumps({
            'dcPinnedFilterRefresh': {
                'target': '#hq-hx-pinned-filters',
            },
            'dcFilterRefresh': {
                'target': '#hq-hx-active-filters',
            },
        })
        return response

    @hq_hx_action('post')
    def select_record(self, request, *args, **kwargs):
        """
        Selects (or de-selects) a single record.
        """
        doc_id = request.POST['record_id']
        is_selected = request.POST.get('is_selected') is not None
        if is_selected:
            self.session.select_record(doc_id)
        else:
            self.session.deselect_record(doc_id)
        return self.render_htmx_no_response(request, *args, **kwargs)

    @hq_hx_action('post')
    def select_page(self, request, *args, **kwargs):
        """
        Selects (or de-selects) all records on the current page.
        """
        select_page = request.POST.get('select_page') is not None
        doc_ids = request.POST.getlist('recordIds')
        if select_page:
            self.session.select_multiple_records(doc_ids)
        else:
            self.session.deselect_multiple_records(doc_ids)
        return self.render_htmx_no_response(request, *args, **kwargs)

    @hq_hx_action('post')
    def deselect_all(self, request, *args, **kwargs):
        """
        De-selects all records in the current filtered view.
        """
        self.session.deselect_all_records_in_queryset()
        return self.get(request, *args, **kwargs)

    @hq_hx_action('post')
    def select_all(self, request, *args, **kwargs):
        """
        Selects all records in the current filtered view.
        """
        self.session.select_all_records_in_queryset()
        return self.get(request, *args, **kwargs)


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
