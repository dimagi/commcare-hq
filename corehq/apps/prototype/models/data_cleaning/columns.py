from abc import ABCMeta, abstractmethod

from memoized import memoized
from django.template import Context, Template
from django.template.loader import get_template
from django.utils.translation import gettext as _

from django_tables2 import columns

from corehq.apps.prototype.models.data_cleaning.cache_store import (
    FilterColumnStore,
    FakeCaseDataStore,
    FakeCaseDataHistoryStore,
)
from corehq.apps.prototype.models.data_cleaning.filters import ColumnFilter


class SystemPropertyColumn(columns.TemplateColumn):
    template_name = "prototype/data_cleaning/partials/columns/system_property_column.html"

    def __init__(self, *args, **kwargs):
        super().__init__(
            template_name=self.template_name,
            *args, **kwargs
        )


class EditableColumn(columns.TemplateColumn):
    template_name = "prototype/data_cleaning/partials/columns/editable_column.html"

    def __init__(self, *args, **kwargs):
        super().__init__(
            template_name=self.template_name,
            *args, **kwargs
        )

    @staticmethod
    def get_edited_slug(slug):
        return f"{slug}__edited"

    def get_cell_context(self, record, table, value, bound_column, bound_row):
        edited_accessor = self.get_edited_slug(bound_column.accessor)
        return {
            "table": table,
            "default": bound_column.default,
            "column": bound_column,
            "record": record,
            "value": value,
            "edited_value": record.get(edited_accessor),
            "row_counter": bound_row.row_counter,
        }

    def render(self, record, table, value, bound_column, **kwargs):
        # Taken from the original TemplateColumn.render, adding direct context for the edited value
        context = getattr(table, "context", Context())
        additional_context = self.get_cell_context(
            record, table, value, bound_column, kwargs["bound_row"]
        )
        additional_context.update(self.extra_context)
        with context.update(additional_context):
            if self.template_code:
                return Template(self.template_code).render(context)
            else:
                return get_template(self.template_name).render(context.flatten())


class BaseDataCleaningColumnManager(metaclass=ABCMeta):
    configure_columns_form_id = "configure-columns-form"
    filter_form_id = "filter-columns-form"
    clean_data_form_id = "clean-columns-form"
    filter_store_class = None
    column_filter_class = ColumnFilter
    data_store_class = None
    data_store_history_class = None

    def __init__(self, request):
        self.request = request

    @classmethod
    @abstractmethod
    def get_available_columns(cls):
        """
        Should return a list of DjangoTable (slug, Column) tuples:
        eg:
            return [
                ("full_name", EditableColumn(
                    verbose_name=gettext_lazy("Name"),
                )),
            ]
        """
        pass

    def has_edits(self):
        rows = self.data_store.get()
        for row in rows:
            edited_keys = [k for k in row.keys() if k.endswith("__edited")]
            if edited_keys:
                return True
        return False

    @property
    def data_store(self):
        return self.data_store_class(self.request)

    @property
    def history_store(self):
        return self.data_store_history_class(self.request)

    @property
    def filter_store(self):
        return self.filter_store_class(self.request)

    def has_filters(self):
        return len(self.filter_store.get()) > 0

    def clear_filters(self):
        self.filter_store.set([])

    @classmethod
    def get_column_map(cls):
        return dict(cls.get_available_columns())

    def get_filters(self):
        column_map = self.get_column_map()
        return [
            self.column_filter_class(column_map, *args)
            for args in self.filter_store.get()
        ]

    def get_filtered_data(self):
        data = self.data_store.get()
        for column_filter in self.get_filters():
            data = column_filter.apply_filter(data)
        return data

    def get_all_rows(self):
        return self.data_store.get()

    @property
    def total_records(self):
        return len(self.data_store.get())

    def update_all_rows(self, updated_rows):
        return self.data_store.set(updated_rows)

    def is_row_selected(self, row):
        return row['selected'] and row['id'] in self.filtered_record_ids

    def update_rows_with_function(self, update_fn, only_selected=False, clear_history=False):
        all_rows = self.get_all_rows()
        changed_row_ids = []
        for row in all_rows:
            if only_selected and not self.is_row_selected(row):
                continue
            has_changes = update_fn(row)
            if has_changes:
                changed_row_ids.append(row['id'])
        self.update_all_rows(all_rows)
        if clear_history and only_selected:
            self.clear_selected_history(changed_row_ids)
        elif clear_history:
            self.clear_history()

    def clear_changes(self, only_selected=False):
        if not self.has_edits():
            return

        def _clear_changes_to_row(row):
            edited_keys = [k for k in row.keys() if k.endswith('__edited')]
            for edited_key in edited_keys:
                del row[edited_key]
            return len(edited_keys) > 0

        self.update_rows_with_function(
            _clear_changes_to_row,
            only_selected=only_selected,
            clear_history=True
        )

    def apply_changes(self, only_selected=False):
        if not self.has_edits():
            return

        def _apply_changes_to_row(row):
            edited_keys = [k for k in row.keys() if k.endswith('__edited')]
            for edited_key in edited_keys:
                original_key = edited_key.replace('__edited', '')
                edited_value = row[edited_key]
                row[original_key] = None if edited_value is Ellipsis else edited_value
                del row[edited_key]
            return len(edited_keys) > 0

        self.update_rows_with_function(
            _apply_changes_to_row,
            only_selected=only_selected,
            clear_history=True
        )

    @property
    @memoized
    def filtered_record_ids(self):
        return [record["id"] for record in self.get_filtered_data()]

    def add_filter(self, slug, match, value, use_regex):
        filters = self.filter_store.get()
        filters.append([slug, match, value, use_regex])
        self.filter_store.set(filters)

    def reorder_filters(self, filter_slugs):
        stored_filters = self.filter_store.get()
        slug_to_filter = dict((f[0], f) for f in stored_filters)
        reordered_filters = []
        for slug in filter_slugs:
            if slug_to_filter.get(slug):
                reordered_filters.append(slug_to_filter[slug])
        self.filter_store.set(reordered_filters)

    def delete_filter(self, index):
        filters = self.filter_store.get()
        try:
            del filters[index]
        except IndexError:
            pass
        self.filter_store.set(filters)

    @classmethod
    def get_visible_columns(cls, column_slugs):
        column_map = cls.get_column_map()
        visible_columns = [(slug, column_map[slug]) for slug in column_slugs]
        return visible_columns

    @classmethod
    def get_editable_column_options(cls):
        return [
            (slug, col.verbose_name) for slug, col in cls.get_available_columns()
            if type(col) is EditableColumn
        ]

    def has_history(self):
        return bool(self.history_store.get())

    def clear_history(self):
        if self.has_history():
            self.history_store.delete()

    def clear_selected_history(self, row_ids):
        if not self.has_history():
            return
        histories = self.history_store.get()
        all_rows = self.data_store.get()
        for ind in range(0, len(histories)):
            for row_id in row_ids:
                histories[ind][row_id] = all_rows[row_id]
        self.history_store.set(histories)

    def make_history_snapshot(self):
        histories = self.history_store.get()
        rows = self.data_store.get()
        histories.append(rows)
        if len(histories) > 21:
            del histories[0]
        self.history_store.set(histories)

    def rollback_history(self):
        if self.has_history():
            histories = self.history_store.get()

            previous_rows = histories[-1]
            current_rows = self.data_store.get()
            for ind, row in enumerate(previous_rows):
                row["selected"] = current_rows[ind]["selected"]

            self.data_store.set(previous_rows)
            if len(histories) == 1:
                self.history_store.delete()
            else:
                self.history_store.set(histories[:-1])


class CaseDataCleaningColumnManager(BaseDataCleaningColumnManager):
    filter_store_class = FilterColumnStore
    data_store_class = FakeCaseDataStore
    data_store_history_class = FakeCaseDataHistoryStore

    @classmethod
    def get_available_columns(cls):
        available_columns = [
            ("name", EditableColumn(
                verbose_name=_("name"),
            )),
        ]
        case_properties = [
            'conducted_delivery',
            'date_of_delivery',
            'delivery_location',
            'dob',
            'edd',
            'hight',
            'height',
            'lmp',
            'mother_status',
            'spoken_language',
            'time_of_day',
        ]
        available_columns.extend([(prop, EditableColumn(verbose_name=prop))
                        for prop in case_properties])
        available_columns.extend([
            ("owner_name", SystemPropertyColumn(
                verbose_name=_("Owner"),
            )),
            ("opened_date", SystemPropertyColumn(
                verbose_name=_("Created Date"),
            )),
            ("opened_by", SystemPropertyColumn(
                verbose_name=_("Created By"),
            )),
            ("last_modified_date", SystemPropertyColumn(
                verbose_name=_("Modified Date"),
            )),
            ("last_modified_by_user_username", SystemPropertyColumn(
                verbose_name=_("Modified By"),
            )),
            ("status", SystemPropertyColumn(
                verbose_name=_("Status"),
            )),
            ("closed_date", SystemPropertyColumn(
                verbose_name=_("Closed Date"),
            )),
            ("closed_by_username", SystemPropertyColumn(
                verbose_name=_("Closed By"),
            )),
        ])
        return available_columns
