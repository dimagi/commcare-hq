import json

from django.http import Http404
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from django_tables2 import columns, config, rows

from corehq import toggles
from corehq.apps.prototype.models.data_cleaning.cache_store import VisibleColumnStore, FakeCaseDataStore
from corehq.apps.prototype.models.data_cleaning.columns import EditableColumn
from corehq.apps.prototype.models.data_cleaning.filters import ColumnFilter
from corehq.apps.prototype.models.data_cleaning.tables import FakeCaseTable
from corehq.apps.prototype.views.htmx.pagination import SavedPaginatedTableView


@method_decorator(toggles.SAAS_PROTOTYPE.required_decorator(), name='dispatch')
class DataCleaningTableView(SavedPaginatedTableView):
    urlname = "prototype_data_cleaning_htmx"
    table_class = FakeCaseTable
    data_store = FakeCaseDataStore
    template_name = 'prototype/htmx/single_table.html'

    def get_queryset(self):
        table_data = FakeCaseDataStore(self.request).get()
        return ColumnFilter.filter_table_from_cache(
            self.request, table_data
        )

    @staticmethod
    def is_record_checked(value, record):
        return record.get("selected", False)

    @staticmethod
    def get_checkbox_hx_vals(record, value):
        return json.dumps({
            "toggle": record["id"],
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
                        "name": "selection_all",
                        "value": "all",
                        "data-select-all": "true",
                        # htmx
                        "hx-swap": "none",
                        "hx-post": self.request.get_full_path(),
                        "hx-vals": json.dumps({
                            "selectPage": self.get_current_page(),
                        }),
                        # alpine
                        ":checked": "page_num_selected == page_total_records",
                    },
                    "td__input": {
                        "class": "form-check-input js-select-row",
                        # htmx
                        "hx-swap": "none",
                        "hx-post": self.request.get_full_path(),
                        "hx-vals": self.get_checkbox_hx_vals,
                        # alpine
                        "x-init": "if ($el.checked) { page_num_selected++; }",
                        "@click": "if ($event.target.checked != is_selected) {"
                                  "  $event.target.checked ? num_selected++ : num_selected--;"
                                  "  $event.target.checked ? page_num_selected++ : page_num_selected--; "
                                  "}"
                                  "is_selected = $event.target.checked;"
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

    def get_current_page(self):
        page_kwarg = self.page_kwarg
        page = self.kwargs.get(page_kwarg) or self.request.GET.get(page_kwarg) or 1
        return page

    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except Http404 as err:
            page = self.get_current_page()
            if int(page) > 1:
                return redirect(self.urlname)
            else:
                raise err

    def post(self, request, *args, **kwargs):
        if 'selectAll' in request.POST:
            is_selected = request.POST['selectAll'] == 'true'
            self.select_all(is_selected)

        if 'selectPage' in request.POST:
            is_selected = 'selection_all' in request.POST
            self.select_page(request.POST.getlist('rowIds'), is_selected)

        if 'toggle' in request.POST:
            is_selected = 'selection' in request.POST
            self.select_row(int(request.POST['toggle']), is_selected)

        if 'clearFilters' in request.POST:
            FakeCaseTable.clear_filters(request)

        if 'applyEdits' in request.POST:
            self.apply_edits()

        return self.get(request, *args, **kwargs)

    def select_row(self, row_id, is_selected):
        data_store = FakeCaseDataStore(self.request)
        all_rows = data_store.get()
        all_rows[row_id]['selected'] = is_selected
        data_store.set(all_rows)

    def select_all(self, is_selected):
        data_store = FakeCaseDataStore(self.request)
        all_rows = data_store.get()
        for row in all_rows:
            row['selected'] = is_selected
        data_store.set(all_rows)

    def select_page(self, row_ids, is_selected):
        data_store = FakeCaseDataStore(self.request)
        all_rows = data_store.get()
        for row_id in row_ids:
            all_rows[int(row_id)]['selected'] = is_selected
        data_store.set(all_rows)

    def cancel_edit_for_cell(self, row_id, column_slug):
        data_store = FakeCaseDataStore(self.request)
        all_rows = data_store.get()
        edited_slug = EditableColumn.get_edited_slug(column_slug)
        if edited_slug in all_rows[row_id]:
            del all_rows[row_id][edited_slug]
        data_store.set(all_rows)

    def edit_cell_value(self, row_id, column_slug, new_value):
        data_store = FakeCaseDataStore(self.request)
        all_rows = data_store.get()
        edited_slug = EditableColumn.get_edited_slug(column_slug)
        if all_rows[row_id][column_slug] != new_value:
            all_rows[row_id][edited_slug] = new_value
        data_store.set(all_rows)

    def apply_edits(self):
        data_store = FakeCaseDataStore(self.request)
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


@method_decorator(toggles.SAAS_PROTOTYPE.required_decorator(), name='dispatch')
class DataCleaningCellEditView(TemplateView):
    urlname = "prototype_data_cleaning_edit_cell"
    template_name = EditableColumn.template_name
    table_view_class = DataCleaningTableView

    http_method_names = [
        "post",
    ]

    @property
    def data_store(self):
        return self.table_view_class.data_store

    @property
    def column_slug(self):
        slug = self.request.POST['column']
        if not slug:
            raise Http404("column must be present in request.POST")
        return slug

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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        column = dict(FakeCaseTable.available_columns)[self.column_slug]
        record = self.get_record()
        value = record[self.column_slug]

        table_class = self.table_view_class.table_class
        table = config.RequestConfig(self.request).configure(table_class(data=[]))

        bound_row = rows.BoundRow(record, table=table)
        bound_column = columns.BoundColumn(table, column, self.column_slug)

        cell_context = column.get_cell_context(
            record, table, value, bound_column, bound_row
        )

        context.update(cell_context)
        return context

    def post(self, request, *args, **kwargs):
        actions = {
            'cancelEdit': self.cancel_edit,
            "editCellValue": self.edit_cell_value,
        }
        for action_slug, action_fn in actions.items():
            if action_slug in self.request.POST:
                actions[action_slug]()
        return super().get(request, *args, **kwargs)

    def cancel_edit(self):
        data_store = self.data_store(self.request)
        all_rows = data_store.get()
        edited_slug = EditableColumn.get_edited_slug(self.column_slug)
        if edited_slug in all_rows[self.record_id]:
            del all_rows[self.record_id][edited_slug]
        data_store.set(all_rows)

    def edit_cell_value(self):
        data_store = self.data_store(self.request)
        all_rows = data_store.get()
        edited_slug = EditableColumn.get_edited_slug(self.column_slug)
        new_value = self.request.POST['newValue']
        original_value = all_rows[self.record_id][self.column_slug]
        if original_value != new_value:
            # edit value only if it differs from the original value
            all_rows[self.record_id][edited_slug] = new_value
        elif original_value == new_value and all_rows[self.record_id].get(edited_slug):
            # delete an existing edited value
            del all_rows[self.record_id][edited_slug]
        data_store.set(all_rows)
