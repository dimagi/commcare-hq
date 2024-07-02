import json

from django.http import Http404
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django_tables2 import columns, config, rows

from corehq import toggles
from corehq.apps.prototype.models.data_cleaning.cache_store import VisibleColumnStore, FakeCaseDataStore
from corehq.apps.prototype.models.data_cleaning.columns import EditableColumn
from corehq.apps.prototype.models.data_cleaning.filters import ColumnFilter
from corehq.apps.prototype.models.data_cleaning.tables import FakeCaseTable
from corehq.apps.prototype.views.data_cleaning.mixins import HtmxActionMixin, hx_action
from corehq.apps.prototype.views.htmx.pagination import SavedPaginatedTableView


@method_decorator(toggles.SAAS_PROTOTYPE.required_decorator(), name='dispatch')
class DataCleaningTableView(HtmxActionMixin, SavedPaginatedTableView):
    urlname = "prototype_data_cleaning_htmx"
    table_class = FakeCaseTable
    data_store = FakeCaseDataStore
    template_name = 'prototype/htmx/single_table.html'

    def get_queryset(self):
        table_data = self.data_store(self.request).get()
        return ColumnFilter.filter_table_from_cache(
            self.request, table_data
        )

    @staticmethod
    def is_record_checked(value, record):
        return record.get("selected", False)

    @staticmethod
    def get_checkbox_hx_vals(record, value):
        return json.dumps({
            "recordId": record["id"],
        })

    def get_table_kwargs(self):
        visible_columns = VisibleColumnStore(self.request).get()
        extra_columns = [
            ("selection", columns.CheckBoxColumn(
                accessor="id",
                attrs={
                    "th": {
                        "class": "select-header"
                    },
                    "th__input": {
                        "class": "form-check-input",
                        "name": "selectionAll",
                        "value": "all",
                        "data-select-all": "true",
                        # htmx
                        "hx-swap": "none",
                        "hx-post": self.request.get_full_path(),
                        "hx-action": "select_page",
                        # alpine
                        # `pageNumRecordsSelected`, `pageTotalRecords`: defined in table_with_status_bar.html
                        ":checked": "pageNumRecordsSelected == pageTotalRecords",
                    },
                    "td__input": {
                        "class": "form-check-input js-select-row",
                        # htmx
                        "hx-swap": "none",
                        "hx-post": self.request.get_full_path(),
                        "hx-action": "select_row",
                        "hx-vals": self.get_checkbox_hx_vals,
                        # alpine
                        "x-init": "if ($el.checked) { pageNumRecordsSelected++; }",
                        # `isRowSelected`: defined in FakeCaseTable.Meta.row_attrs
                        # `pageNumRecordsSelected`, `numRecordsSelected`: defined in table_with_status_bar.html
                        "@click": "if ($event.target.checked != isRowSelected) {"
                                  "  $event.target.checked ? numRecordsSelected++ : numRecordsSelected--;"
                                  "  $event.target.checked ? pageNumRecordsSelected++ : pageNumRecordsSelected--; "
                                  "}"
                                  "isRowSelected = $event.target.checked;"
                    },
                },
                orderable=False,
                checked=self.is_record_checked,
            ))
        ]
        extra_columns.extend(self.table_class.get_visible_columns(visible_columns))
        return {
            'template_name': "prototype/data_cleaning/partials/tables/table_with_status_bar.html",
            'extra_columns': extra_columns,
        }

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
    def apply_edits(self, request, *args, **kwargs):
        data_store = self.data_store(self.request)
        all_rows = data_store.get()
        for row in all_rows:
            if not row['selected']:
                continue
            edited_keys = [k for k in row.keys() if k.endswith('__edited')]
            for edited_key in edited_keys:
                original_key = edited_key.replace('__edited', '')
                row[original_key] = row[edited_key]
                del row[edited_key]
        data_store.set(all_rows)
        return self.get(request, *args, **kwargs)

    @hx_action('post')
    def clear_filters(self, request, *args, **kwargs):
        self.table_class.clear_filters(request)
        return self.get(request, *args, **kwargs)

    @hx_action('post')
    def select_all(self, request, *args, **kwargs):
        is_selected = request.POST['selectAll'] == 'true'
        data_store = self.data_store(self.request)
        all_rows = data_store.get()
        for row in all_rows:
            row['selected'] = is_selected
        data_store.set(all_rows)
        return self.get(request, *args, **kwargs)

    @hx_action('post')
    def select_page(self, request, *args, **kwargs):
        data_store = self.data_store(self.request)
        is_selected = 'selectionAll' in request.POST

        # `pageRowIds` is inserted in htmx:beforeSend event listener
        # in data_cleaning.js and, selecting values for checkboxes with
        # the `js-select-row` css class.
        row_ids = request.POST.getlist('pageRowIds')

        all_rows = data_store.get()
        for row_id in row_ids:
            all_rows[int(row_id)]['selected'] = is_selected
        data_store.set(all_rows)
        return self.render_htmx_no_response(request, *args, **kwargs)

    @hx_action('post')
    def select_row(self, request, *args, **kwargs):
        is_selected = 'selection' in request.POST
        data_store = self.data_store(self.request)
        all_rows = data_store.get()
        all_rows[self.record_id]['selected'] = is_selected
        data_store.set(all_rows)
        return self.render_htmx_no_response(request, *args, **kwargs)

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
        all_rows = self.data_store(self.request).get()
        return all_rows[self.record_id]

    @property
    def column_slug(self):
        slug = self.request.POST['column']
        if not slug:
            raise Http404("column must be present in request.POST")
        return slug

    def get_column(self):
        return dict(self.table_class.available_columns)[self.column_slug]

    def get_cell_context_data(self, request):
        column = self.get_column()
        record = self.get_record()
        value = record[self.column_slug]

        table = config.RequestConfig(request).configure(
            self.table_class(data=[])
        )

        bound_row = rows.BoundRow(record, table=table)
        bound_column = columns.BoundColumn(table, column, self.column_slug)

        return column.get_cell_context(
            record, table, value, bound_column, bound_row
        )

    def render_table_cell_response(self, request, *args, **kwargs):
        context = self.get_cell_context_data(request)
        self.template_name = self.get_column().template_name
        return self.render_htmx_partial_response(
            request, self.get_column().template_name, context
        )

    @hx_action('post')
    def cancel_edit(self, request, *args, **kwargs):
        data_store = self.data_store(self.request)
        all_rows = data_store.get()
        edited_slug = EditableColumn.get_edited_slug(self.column_slug)
        if edited_slug in all_rows[self.record_id]:
            del all_rows[self.record_id][edited_slug]
        data_store.set(all_rows)
        return self.render_table_cell_response(request, *args, **kwargs)

    @hx_action('post')
    def edit_cell_value(self, request, *args, **kwargs):
        data_store = self.data_store(self.request)
        all_rows = data_store.get()
        edited_slug = EditableColumn.get_edited_slug(self.column_slug)
        new_value = request.POST['newValue']
        original_value = all_rows[self.record_id][self.column_slug]
        if original_value != new_value:
            # edit value only if it differs from the original value
            all_rows[self.record_id][edited_slug] = new_value
        elif original_value == new_value and all_rows[self.record_id].get(edited_slug):
            # delete an existing edited value
            del all_rows[self.record_id][edited_slug]
        data_store.set(all_rows)
        return self.render_table_cell_response(request, *args, **kwargs)
