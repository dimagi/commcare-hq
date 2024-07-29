from django_tables2 import columns, tables


class FakeCaseTable(tables.Table):
    container_id = "fake-case-table"
    loading_indicator_id = "loading-table-hx"

    class Meta:
        attrs = {
            'class': 'table table-striped align-middle',
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
        self.column_manager = kwargs.pop('column_manager')
        super().__init__(*args, **kwargs)
        self.num_selected_records = self.get_num_selected_records(self.data)

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
