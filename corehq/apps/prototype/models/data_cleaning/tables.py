from django.utils.translation import gettext_lazy
from django_tables2 import columns, tables

from corehq.apps.prototype.models.data_cleaning.cache_store import FilterColumnStore


class FakeCaseTable(tables.Table):
    css_id = "fake-case-table"
    filter_form_id = "filter-columns-form"
    available_columns = [
        ("full_name", columns.Column(
            verbose_name=gettext_lazy("Name"),
        )),
        ("color", columns.Column(
            verbose_name=gettext_lazy("Color"),
        )),
        ("big_cat", columns.Column(
            verbose_name=gettext_lazy("Big Cats"),
        )),
        ("planet", columns.Column(
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
            "x-data": "{ is_selected: $el.firstElementChild.firstElementChild.checked }",
            ":class": "{ 'table-primary': is_selected }",
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

    def has_filters(self):
        if hasattr(self, 'request'):
            return len(FilterColumnStore(self.request).get()) > 0
        return False

    @classmethod
    def clear_filters(cls, request):
        FilterColumnStore(request).set([])
