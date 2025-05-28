import json

from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator

from corehq.apps.data_cleaning.columns import EditableHtmxColumn
from corehq.apps.data_cleaning.decorators import require_bulk_data_cleaning_cases
from corehq.apps.data_cleaning.models import BulkEditSession
from corehq.apps.data_cleaning.tables import (
    EditCasesTable,
    RecentCaseSessionsTable,
)
from corehq.apps.data_cleaning.tasks import commit_data_cleaning
from corehq.apps.data_cleaning.views.mixins import BulkEditSessionViewMixin
from corehq.apps.domain.decorators import LoginAndDomainMixin
from corehq.apps.domain.views import DomainViewMixin
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.hqwebapp.tables.pagination import (
    HtmxInvalidPageRedirectMixin,
    SelectablePaginatedTableView,
)
from corehq.util.htmx_action import HqHtmxActionMixin, hq_hx_action


@method_decorator([
    use_bootstrap5,
    require_bulk_data_cleaning_cases,
], name='dispatch')
class BaseDataCleaningTableView(LoginAndDomainMixin, DomainViewMixin, SelectablePaginatedTableView):
    pass


class EditCasesTableView(BulkEditSessionViewMixin,
                         HtmxInvalidPageRedirectMixin, HqHtmxActionMixin, BaseDataCleaningTableView):
    urlname = "bulk_edit_cases_table"
    table_class = EditCasesTable

    def get_host_url(self):
        from corehq.apps.data_cleaning.views.main import BulkEditCasesSessionView
        return reverse(BulkEditCasesSessionView.urlname, args=(self.domain, self.session_id,))

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
        response = self.get(request, *args, **kwargs)
        if self.session.can_select_all(
            table_num_records=response.context_data['paginator'].count
        ):
            self.session.select_all_records_in_queryset()
            return self.add_gtm_event_to_response(
                response,
                "bulk_edit_select_all_records",
                {
                    "session_type": self.session.session_type,
                    "num_records": response.context_data['paginator'].count,
                },
            )
        response['HX-Trigger'] = json.dumps({
            'showDataCleaningModal': {
                'target': '#select-all-not-possible-modal',
            },
        })
        return self.add_gtm_event_to_response(
            response,
            "bulk_edit_select_all_records_not_possible",
            {
                "session_type": self.session.session_type,
                "num_records": response.context_data['paginator'].count,
            },
        )

    @hq_hx_action("post")
    def apply_all_changes(self, request, *args, **kwargs):
        # even if a user hacks their way to more edits in this session, they can never apply those edits
        if not self.session.is_read_only:
            self.session.committed_on = timezone.now()
            self.session.save()
            commit_data_cleaning.delay(self.session.session_id)
        response = self.render_htmx_no_response(request, *args, **kwargs)
        response['HX-Trigger'] = json.dumps({
            'dcRefreshStatusModal': {
                'target': '#session-status-modal-body',
            },
        })
        return self.add_gtm_event_to_response(
            response,
            "bulk_edit_apply_all_changes",
            {
                "session_type": self.session.session_type,
            },
        )

    @hq_hx_action("post")
    def undo_last_change(self, request, *args, **kwargs):
        self.session.undo_last_change()
        response = self._trigger_clean_form_refresh(
            self.get(request, *args, **kwargs)
        )
        return self.add_gtm_event_to_response(
            response,
            "bulk_edit_undo_last_change",
            {
                "session_type": self.session.session_type,
            },
        )

    @hq_hx_action("post")
    def clear_all_changes(self, request, *args, **kwargs):
        self.session.clear_all_changes()
        response = self._trigger_clean_form_refresh(
            self.get(request, *args, **kwargs)
        )
        return self.add_gtm_event_to_response(
            response,
            "bulk_edit_clear_all_changes",
            {
                "session_type": self.session.session_type,
            },
        )

    def _trigger_clean_form_refresh(self, response):
        response['HX-Trigger'] = json.dumps({
            'dcEditFormRefresh': {
                'target': '#hq-hx-edit-selected-records-form',
            },
        })
        return response

    def _render_table_cell_response(self, doc_id, column, request, *args, **kwargs):
        """
        Returns an a partial HttpResponse for the table cell,
        using the `EditableHtmxColumn` template and context.
        """
        record = self.table_class.record_class(
            self.session.get_document_from_queryset(doc_id),
            self.request,
            session=self.session,
        )
        table = self.table_class(session=self.session, data=self.session.get_queryset())
        context = EditableHtmxColumn.get_htmx_partial_response_context(
            column,
            record,
            table,
        )
        response = self.render_htmx_partial_response(
            request, EditableHtmxColumn.template_name, context
        )
        response['HX-Trigger'] = json.dumps({
            "updateChanges": {
                "hasChanges": self.session.has_changes(),
            },
        })
        return response

    def _get_cell_request_details(self, request):
        """
        Returns the details of the cell request.
        """
        doc_id = request.POST["record_id"]
        column = self.session.columns.get(column_id=request.POST["column_id"])
        return doc_id, column

    @hq_hx_action("post")
    def cell_reset_changes(self, request, *args, **kwargs):
        """
        Effectively resets/removes any changes made to a record's prop_id.
        """
        doc_id, column = self._get_cell_request_details(request)
        edit_record = self.session.records.get(doc_id=doc_id)
        edit_record.reset_changes(column.prop_id)
        return self._render_table_cell_response(
            doc_id, column, request, *args, **kwargs
        )

    @hq_hx_action("post")
    def cell_inline_edit(self, request, *args, **kwargs):
        """
        Commits the inline edit action for a cell.
        """
        doc_id, column = self._get_cell_request_details(request)
        value = request.POST["newValue"]
        self.session.apply_inline_edit(doc_id, column.prop_id, value)
        return self._render_table_cell_response(
            doc_id, column, request, *args, **kwargs
        )


class RecentCaseSessionsTableView(BaseDataCleaningTableView):
    urlname = "recent_bulk_edit_case_sessions_table"
    table_class = RecentCaseSessionsTable

    def get_queryset(self):
        return [
            self._get_record(session) if session.committed_on else self._get_active_record(session)
            for session in BulkEditSession.objects.all_sessions(self.request.user, self.domain)
        ]

    def _get_session_url(self, session):
        from corehq.apps.data_cleaning.views.main import BulkEditCasesSessionView
        return reverse(BulkEditCasesSessionView.urlname, args=(session.domain, session.session_id))

    def _get_record(self, session):
        return {
            "is_active": False,
            "committed_on": session.committed_on,
            "completed_on": session.completed_on,
            "case_type": session.identifier,
            "case_count": session.num_changed_records,
            "percent": session.percent_complete,
            "form_ids_url": reverse('download_form_ids', args=(session.domain, session.session_id)),
            "has_form_ids": bool(len(session.form_ids)),
            "session_url": self._get_session_url(session),
        }

    def _get_active_record(self, session):
        return {
            "is_active": True,
            "case_type": session.identifier,
            "percent": 0,
            "session_url": self._get_session_url(session),
        }
