import json
import random
import time

from memoized import memoized
from django.http import Http404
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django_tables2 import columns, config, rows

from corehq import toggles
from corehq.apps.prototype.models.data_cleaning.cache_store import (
    VisibleColumnStore,
    FakeCaseDataStore,
    SlowSimulatorStore,
    ApplyChangesSimulationStore,
)
from corehq.apps.prototype.models.data_cleaning.columns import EditableColumn, CaseDataCleaningColumnManager
from corehq.apps.prototype.models.data_cleaning.tables import FakeCaseTable
from corehq.apps.prototype.views.data_cleaning.mixins import HtmxActionMixin, hx_action
from corehq.apps.prototype.views.htmx.pagination import SavedPaginatedTableView


@method_decorator(toggles.SAAS_PROTOTYPE.required_decorator(), name='dispatch')
class DataCleaningTableView(HtmxActionMixin, SavedPaginatedTableView):
    urlname = "prototype_data_cleaning_htmx"
    table_class = FakeCaseTable
    column_manager_class = CaseDataCleaningColumnManager
    data_store_class = FakeCaseDataStore
    template_name = 'prototype/htmx/single_table.html'
    paginate_by = 10

    @property
    @memoized
    def column_manager(self):
        return self.column_manager_class(self.request)

    @property
    def data_store(self):
        return self.data_store_class(self.request)

    def get_queryset(self):
        return self.column_manager.get_filtered_table_data(
            self.data_store_class(self.request).get()
        )

    @property
    @memoized
    def record_ids(self):
        return [record["id"] for record in self.get_queryset()]

    def get_table_kwargs(self):
        extra_columns = [self.table_class.get_row_select_column(
            extra_select_all_rows_attrs={
                "class": "form-check-input js-disable-on-select-all",
                "name": "selectionAll",  # used in hx_action response below
                "value": "all",
                # htmx
                "hx-swap": "none",
                "hx-post": self.request.get_full_path(),
                "hq-hx-action": "select_page",
                "hx-disabled-elt": ".js-disable-on-select-all",
                "hq-hx-table-select-all": "js-select-row",
                "hq-hx-table-select-all-trigger": "click",
                "hq-hx-table-select-all-param": "pageRowIds",
            },
            extra_select_row_attrs={
                "class": "form-check-input js-select-row js-disable-on-select-all",
                # htmx
                "hx-swap": "none",
                "hx-post": self.request.get_full_path(),
                "hq-hx-action": "select_row",
                "hx-vals": self.get_checkbox_hx_vals,
                "hx-disabled-elt": "this",
            },
            extra_select_checkbox_kwargs={
                "accessor": "id",
                "checked": self.is_record_checked,
            },
        )]
        extra_columns.extend(self.column_manager.get_visible_columns(
            VisibleColumnStore(self.request).get()
        ))
        return {
            'column_manager': self.column_manager,
            'extra_columns': extra_columns,
        }

    @staticmethod
    def is_record_checked(value, record):
        return record.get("selected", False)

    @staticmethod
    def get_checkbox_hx_vals(record, value):
        return json.dumps({
            "recordId": record["id"],
        })

    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except Http404 as err:
            page_kwarg = self.page_kwarg
            page = self.kwargs.get(page_kwarg) or self.request.GET.get(page_kwarg) or 1
            if int(page) > 1:
                return redirect(self.urlname)
            else:
                raise err

    @hx_action('post')
    def clear_filters(self, request, *args, **kwargs):
        self.column_manager.clear_filters()
        return self.get(request, *args, **kwargs)

    @hx_action('post')
    def select_all(self, request, *args, **kwargs):
        is_selected = request.POST['selectAll'] == 'true'
        all_rows = self.data_store.get()
        for row in all_rows:
            row['selected'] = is_selected
        self.data_store.set(all_rows)
        return self.get(request, *args, **kwargs)

    @hx_action('post')
    def select_page(self, request, *args, **kwargs):
        is_selected = 'selectionAll' in request.POST

        # `pageRowIds` is inserted in htmx:configRequest event listener
        # in data_cleaning.js and, selecting values for checkboxes with
        # the `js-select-row` css class.
        row_ids = request.POST.getlist('pageRowIds')

        all_rows = self.data_store.get()
        for row_id in row_ids:
            all_rows[int(row_id)]['selected'] = is_selected
        self.data_store.set(all_rows)
        return self.render_htmx_no_response(request, *args, **kwargs)

    @hx_action('post')
    def select_row(self, request, *args, **kwargs):
        is_selected = 'selection' in request.POST
        all_rows = self.data_store.get()
        all_rows[self.record_id]['selected'] = is_selected
        self.data_store.set(all_rows)
        return self.render_htmx_no_response(request, *args, **kwargs)

    @hx_action('post')
    def clear_all_edits(self, request, *args, **kwargs):
        self.column_manager.clear_history()
        if self.column_manager.has_edits():
            all_rows = self.data_store.get()
            for row in all_rows:
                edited_keys = [k for k in row.keys() if k.endswith('__edited')]
                for edited_key in edited_keys:
                    del row[edited_key]
            self.data_store.set(all_rows)
        return self.get(request, *args, **kwargs)

    @hx_action('post')
    def clear_selected_edits(self, request, *args, **kwargs):
        if self.column_manager.has_edits():
            all_rows = self.data_store.get()
            changed_row_ids = []
            for row in all_rows:
                if not row['selected']:
                    continue
                if row['id'] not in self.record_ids:
                    continue
                edited_keys = [k for k in row.keys() if k.endswith('__edited')]
                for edited_key in edited_keys:
                    del row[edited_key]
                if edited_keys:
                    changed_row_ids.append(row['id'])
            self.data_store.set(all_rows)
            self.column_manager.clear_selected_history(changed_row_ids)
        return self.get(request, *args, **kwargs)

    @hx_action('post')
    def rollback_history(self, request, *args, **kwargs):
        self.column_manager.rollback_history()
        return self.get(request, *args, **kwargs)

    def render_apply_changes_progress_response(self, request, *args, **kwargs):
        progress_store = ApplyChangesSimulationStore(request)
        progress = progress_store.get()
        context = {
            "progress": progress,
            "show_done": progress >= 100,
        }
        self.template_name = "prototype/data_cleaning/partials/apply_changes_progress_bar.html"
        response = self.render_htmx_partial_response(
            request, self.template_name, context
        )
        if progress > 100:
            progress_store.delete()
            response['HX-Trigger'] = 'hqRefresh'
        return response

    @hx_action('get')
    def simulate_apply_changes_progress(self, request, *args, **kwargs):
        progress_store = ApplyChangesSimulationStore(request)
        time.sleep(.3)
        progress_store.set(progress_store.get() + random.choice(range(10, 30)))
        return self.render_apply_changes_progress_response(request, *args, **kwargs)

    @hx_action('post')
    def apply_selected_changes(self, request, *args, **kwargs):
        has_edits = self.column_manager.has_edits()
        if not has_edits:
            return self.get(request, *args, **kwargs)

        all_rows = self.data_store.get()
        changed_row_ids = []
        for row in all_rows:
            if not row['selected']:
                continue
            if row['id'] not in self.record_ids:
                continue
            edited_keys = [k for k in row.keys() if k.endswith('__edited')]
            for edited_key in edited_keys:
                original_key = edited_key.replace('__edited', '')
                edited_value = row[edited_key]
                row[original_key] = None if edited_value is Ellipsis else edited_value
                del row[edited_key]
            if edited_keys:
                changed_row_ids.append(row['id'])
        self.data_store.set(all_rows)

        self.column_manager.clear_selected_history(changed_row_ids)
        return self.render_apply_changes_progress_response(request, *args, **kwargs)

    @hx_action('post')
    def apply_all_changes(self, request, *args, **kwargs):
        self.column_manager.clear_history()
        has_edits = self.column_manager.has_edits()
        if not has_edits:
            return self.get(request, *args, **kwargs)

        all_rows = self.data_store.get()
        for row in all_rows:
            edited_keys = [k for k in row.keys() if k.endswith('__edited')]
            for edited_key in edited_keys:
                original_key = edited_key.replace('__edited', '')
                edited_value = row[edited_key]
                row[original_key] = None if edited_value is Ellipsis else edited_value
                del row[edited_key]
        self.data_store.set(all_rows)

        return self.render_apply_changes_progress_response(request, *args, **kwargs)

    @property
    def record_id(self):
        record_id = self.request.POST['recordId']
        if not record_id:
            raise Http404("recordId must be present in request.POST")
        try:
            record_id = int(record_id)
        except ValueError:
            raise Http404("recordId should be an integer")
        return record_id

    def get_record(self):
        all_rows = self.data_store.get()
        return all_rows[self.record_id]

    @property
    def column_slug(self):
        slug = self.request.POST['column']
        if not slug:
            raise Http404("column must be present in request.POST")
        return slug

    def get_column(self):
        return dict(self.column_manager_class.get_available_columns())[self.column_slug]

    def get_cell_context_data(self, request):
        column = self.get_column()
        record = self.get_record()
        value = record[self.column_slug]

        table = config.RequestConfig(request).configure(
            self.table_class(
                column_manager=self.column_manager_class(self.request),
                data=[]
            )
        )

        bound_row = rows.BoundRow(record, table=table)
        bound_column = columns.BoundColumn(table, column, self.column_slug)

        return column.get_cell_context(
            record, table, value, bound_column, bound_row
        )

    def render_table_cell_response(self, request, *args, **kwargs):
        context = self.get_cell_context_data(request)
        context['is_partial_update'] = True
        self.template_name = self.get_column().template_name
        return self.render_htmx_partial_response(
            request, self.get_column().template_name, context
        )

    @hx_action('post')
    def cancel_edit(self, request, *args, **kwargs):
        all_rows = self.data_store.get()
        edited_slug = EditableColumn.get_edited_slug(self.column_slug)
        if edited_slug in all_rows[self.record_id]:
            self.column_manager.make_history_snapshot()
            del all_rows[self.record_id][edited_slug]
        self.data_store.set(all_rows)
        return self.render_table_cell_response(request, *args, **kwargs)

    @hx_action('post')
    def edit_cell_value(self, request, *args, **kwargs):
        all_rows = self.data_store.get()
        edited_slug = EditableColumn.get_edited_slug(self.column_slug)
        new_value = request.POST['newValue']
        original_value = all_rows[self.record_id][self.column_slug]
        if original_value != new_value:
            # edit value only if it differs from the original value
            self.column_manager.make_history_snapshot()
            all_rows[self.record_id][edited_slug] = new_value
        elif original_value == new_value and all_rows[self.record_id].get(edited_slug):
            # delete an existing edited value
            self.column_manager.make_history_snapshot()
            del all_rows[self.record_id][edited_slug]
        self.data_store.set(all_rows)
        return self.render_table_cell_response(request, *args, **kwargs)

    @property
    def simulate_slow_response(self):
        return bool(SlowSimulatorStore(self.request).get())

    @property
    def slow_response_time(self):
        return SlowSimulatorStore(self.request).get()
