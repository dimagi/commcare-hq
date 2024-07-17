from abc import ABCMeta, abstractmethod

from django.template import Context, Template
from django.template.loader import get_template
from django.utils.translation import gettext as _

from django_tables2 import columns

from corehq.apps.prototype.models.data_cleaning.cache_store import FilterColumnStore, FakeCaseDataStore
from corehq.apps.prototype.models.data_cleaning.filters import ColumnFilter


class EditableColumn(columns.TemplateColumn):
    template_name = "prototype/data_cleaning/partials/columns/editable_column.html"

    def __init__(self, *args, **kwargs):
        self.cell_edit_url = kwargs.pop('cell_edit_url', None)
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

    @abstractmethod
    def has_edits(self):
        """
        Returns boolean indicating whether edits are applied to the columns
        """
        pass

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

    def get_filtered_table_data(self, table_data):
        for column_filter in self.get_filters():
            table_data = column_filter.apply_filter(table_data)
        return table_data

    def add_filter(self, slug, match, value):
        filters = self.filter_store.get()
        filters.append([slug, match, value])
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


class CaseDataCleaningColumnManager(BaseDataCleaningColumnManager):
    filter_store_class = FilterColumnStore

    @classmethod
    def get_available_columns(cls):
        return [
            ("full_name", EditableColumn(
                verbose_name=_("Name"),
            )),
            ("color", EditableColumn(
                verbose_name=_("Color"),
            )),
            ("big_cat", EditableColumn(
                verbose_name=_("Big Cats"),
            )),
            ("planet", EditableColumn(
                verbose_name=_("Planet"),
            )),
            ("submitted_on", columns.Column(
                verbose_name=_("Submitted On"),
            )),
            ("app", columns.Column(
                verbose_name=_("Application"),
            )),
            ("status", columns.Column(
                verbose_name=_("Status"),
            )),
        ]

    def has_edits(self):
        rows = FakeCaseDataStore(self.request).get()
        for row in rows:
            edited_keys = [k for k in row.keys() if k.endswith("__edited")]
            if edited_keys:
                return True
        return False
