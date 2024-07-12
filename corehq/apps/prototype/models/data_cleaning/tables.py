from django.utils.translation import gettext_lazy
from django_tables2 import columns, tables

from corehq.apps.prototype.models.data_cleaning.cache_store import FilterColumnStore, FakeCaseDataStore
from corehq.apps.prototype.models.data_cleaning.columns import EditableColumn


class FakeCaseTable(tables.Table):
    container_id = "fake-case-table"
    configure_columns_form_id = "configure-columns-form"
    filter_form_id = "filter-columns-form"
    clean_data_form_id = "clean-columns-form"
    loading_indicator_id = "loading-table-hx"
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
        template_name = "prototype/data_cleaning/partials/tables/table_with_status_bar.html"
        row_attrs = {
            "x-data": "{ isRowSelected: $el.firstElementChild.firstElementChild.checked }",
            ":class": "{ 'table-primary': isRowSelected }",
        }

    @classmethod
    def get_select_all_rows_attrs(cls, extra_attrs=None):
        """These are the default attributes for the checkbox input in the header of the
        row selection CheckboxColumn.
        """
        extra_attrs = extra_attrs or {}
        return {
            # `pageNumRecordsSelected`, `pageTotalRecords`: defined in this table's template
            ":checked": "pageNumRecordsSelected == pageTotalRecords",
            **extra_attrs
        }

    @classmethod
    def get_select_row_attrs(cls, extra_attrs=None):
        extra_attrs = extra_attrs or {}
        return {
            "x-init": "if ($el.checked) { pageNumRecordsSelected++; }",
            # `isRowSelected`: defined in row_attrs
            # `pageNumRecordsSelected`, `numRecordsSelected`: defined in this table's template
            "@click": "if ($event.target.checked != isRowSelected) {"
                      "  $event.target.checked ? numRecordsSelected++ : numRecordsSelected--;"
                      "  $event.target.checked ? pageNumRecordsSelected++ : pageNumRecordsSelected--; "
                      "}"
                      "isRowSelected = $event.target.checked;",
            **extra_attrs
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.num_selected_records = self.get_num_selected_records(self.data)

    @classmethod
    def get_visible_columns(cls, column_slugs,
                            allow_row_selection=False,
                            extra_select_checkbox_kwargs=False,
                            extra_select_all_rows_attrs=None,
                            extra_select_row_attrs=None):

        column_map = dict(cls.available_columns)
        visible_columns = [(slug, column_map[slug]) for slug in column_slugs]
        if allow_row_selection:
            visible_columns = [cls.get_row_select_column(
                extra_select_checkbox_kwargs=extra_select_checkbox_kwargs,
                extra_select_all_rows_attrs=extra_select_all_rows_attrs,
                extra_select_row_attrs=extra_select_row_attrs,
            )] + visible_columns
        return visible_columns

    @classmethod
    def get_row_select_column(cls, extra_select_checkbox_kwargs=None,
                              extra_select_all_rows_attrs=None,
                              extra_select_row_attrs=None):
        extra_select_checkbox_kwargs = extra_select_checkbox_kwargs or {}
        return ("selection", columns.CheckBoxColumn(
            attrs={
                "th": {
                    "class": "select-header"
                },
                "th__input": cls.get_select_all_rows_attrs(extra_select_all_rows_attrs),
                "td__input": cls.get_select_row_attrs(extra_select_row_attrs),
            },
            orderable=False,
            **extra_select_checkbox_kwargs,
        ))

    @staticmethod
    def get_num_selected_records(table_data):
        return len([c for c in table_data if c["selected"]])

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
