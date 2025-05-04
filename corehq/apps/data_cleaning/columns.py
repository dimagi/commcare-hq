from django_tables2.columns import (
    TemplateColumn,
    CheckBoxColumn,
    BoundColumn,
)
from django_tables2.utils import AttributeDict

from corehq.toggles import mark_safe
from couchexport.writers import render_to_string


class DataCleaningHtmxColumn(TemplateColumn):
    template_name = "data_cleaning/columns/column_main.html"

    def __init__(self, column_spec, *args, **kwargs):
        """
        Defines the django_tables2 compatible column object
        for the bulk data cleaning feature.

        :param column_spec: BulkEditColumn
        """
        super().__init__(
            template_name=self.template_name,
            accessor=column_spec.prop_id,
            verbose_name=column_spec.label,
            *args, **kwargs
        )
        self.column_spec = column_spec

    @classmethod
    def get_htmx_partial_response_context(cls, column_spec, record, table):
        """
        Returns the context needed for rendering the
        `DataCleaningHtmxColumn` template as an HTMX partial response.

        :param column_spec: BulkEditColumn
        :param record: EditableCaseSearchElasticRecord (or similar)
        :param table: CleanCaseTable (or similar)
        """
        column = cls(column_spec)
        bound_column = BoundColumn(table, column, column_spec.slug)
        value = record[column_spec.prop_id]
        return {
            "column": bound_column,
            "record": record,
            "value": value,
        }


class DataCleaningHtmxSelectionColumn(CheckBoxColumn):
    template_column = "data_cleaning/columns/selection.html"
    template_header = "data_cleaning/columns/selection_header.html"
    select_page_checkbox_id = "id-select-page-checkbox"

    def __init__(self, session, request, select_record_action, select_page_action, *args, **kwargs):
        """
        Defines a django_tables2 compatible column that handles selecting
        records in a data cleaning session.

        :param session: BulkEditSession instance
        :param request: a django request object from the session view
        :param select_record_action: the hq_hx_action from the session view for selecting a row
        :param select_page_action: the hq_hx_action from the session view for selecting all records in a page
        """
        super().__init__(*args, **kwargs)
        self.session = session
        self.request = request
        self.select_record_action = select_record_action
        self.select_page_action = select_page_action
        self.attrs['th'] = {
            'class': 'select-header',
        }

    @classmethod
    def get_selected_record_checkbox_id(self, value):
        return f'id-selected-record-{value}'

    @property
    def header(self):
        general = self.attrs.get("input")
        specific = self.attrs.get("th__input")
        attrs = AttributeDict(specific or general or {})
        return mark_safe(  # nosec: render_to_string below will handle escaping
            render_to_string(
                self.template_header,
                {
                    'hq_hx_action': self.select_page_action,
                    'css_id': self.select_page_checkbox_id,
                    'attrs': attrs,
                },
                request=self.request,
            )
        )

    def render(self, value, bound_column, record):
        general = self.attrs.get("input")
        specific = self.attrs.get("td__input")
        attrs = AttributeDict(specific or general or {})
        return mark_safe(  # nosec: render_to_string below will handle escaping
            render_to_string(
                self.template_column,
                {
                    'hq_hx_action': self.select_record_action,
                    'is_checked': self.is_checked(value, record),
                    'value': value,
                    'css_id': self.get_selected_record_checkbox_id(value),
                    'record': record,
                    'column': bound_column,
                    'attrs': attrs,
                },
                request=self.request,
            )
        )

    def is_checked(self, value, record):
        return self.session.is_record_selected(value)
