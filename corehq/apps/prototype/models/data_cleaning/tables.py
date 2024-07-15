from django.utils.translation import gettext_lazy
from django_tables2 import columns, tables

from corehq.apps.prototype.models.data_cleaning.cache_store import FilterColumnStore, FakeCaseDataStore
from corehq.apps.prototype.models.data_cleaning.columns import EditableColumn


class FakeCaseTable(tables.Table):
    css_id = "fake-case-table"
    configure_columns_form_id = "configure-columns-form"
    filter_form_id = "filter-columns-form"
    clean_data_form_id = "clean-columns-form"
    available_columns = [
        ("full_name", EditableColumn(
            verbose_name=gettext_lazy("Name"),
        )),
        ("color", EditableColumn(
            verbose_name=gettext_lazy("Color"),
        )),
        ("big_cat", EditableColumn(
            verbose_name=gettext_lazy("Big Cats"),
        )),
        ("planet", EditableColumn(
            verbose_name=gettext_lazy("Planet"),
        )),
        ("submitted_on", columns.Column(
            verbose_name=gettext_lazy("Submitted On"),
        )),
        ("app", columns.Column(
            verbose_name=gettext_lazy("Application"),
        )),
        ("status", columns.Column(
            verbose_name=gettext_lazy("Status"),
        )),
    ]

    class Meta:
        attrs = {
            'class': 'table table-striped',
        }
        row_attrs = {
            "x-data": "{ isRowSelected: $el.firstElementChild.firstElementChild.checked }",
            ":class": "{ 'table-primary': isRowSelected }",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.num_selected_records = self.get_num_selected_records(self.data)

    @staticmethod
    def get_num_selected_records(table_data):
        return len([c for c in table_data if c["selected"]])

    @classmethod
    def get_visible_columns(cls, column_slugs):
        column_map = dict(cls.available_columns)
        return [(slug, column_map[slug]) for slug in column_slugs]

    @classmethod
    def get_editable_column_options(cls):
        return [
            (slug, col.verbose_name) for slug, col in cls.available_columns
            if type(col) is EditableColumn
        ]

    def has_filters(self):
        if hasattr(self, 'request'):
            return len(FilterColumnStore(self.request).get()) > 0
        return False

    def has_edits(self):
        # todo make this better...
        #  this was a quick solution for prototype, obviously not production solution
        if hasattr(self, 'request'):
            rows = FakeCaseDataStore(self.request).get()
            for row in rows:
                edited_keys = [k for k in row.keys() if k.endswith("__edited")]
                if edited_keys:
                    return True
        return False

    @classmethod
    def clear_filters(cls, request):
        FilterColumnStore(request).set([])
