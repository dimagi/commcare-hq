from memoized import memoized

from django.utils.translation import gettext_lazy
from django_tables2 import columns, tables

from corehq.apps.data_cleaning.columns import (
    EditableHtmxColumn,
    SelectableHtmxColumn,
)
from corehq.apps.data_cleaning.models.session import (
    BULK_OPERATION_CHUNK_SIZE,
    MAX_RECORDED_LIMIT,
)
from corehq.apps.data_cleaning.records import EditableCaseSearchElasticRecord
from corehq.apps.hqwebapp.tables.elasticsearch.tables import ElasticTable
from corehq.apps.hqwebapp.tables.htmx import BaseHtmxTable


class EditCasesTable(BaseHtmxTable, ElasticTable):
    record_class = EditableCaseSearchElasticRecord
    bulk_action_warning_limit = BULK_OPERATION_CHUNK_SIZE
    max_recorded_limit = MAX_RECORDED_LIMIT

    class Meta(BaseHtmxTable.Meta):
        template_name = "data_cleaning/tables/table_with_controls.html"
        attrs = {
            "class": "table table-striped align-middle",
        }
        row_attrs = {
            "x-data": "{ isRowSelected: $el.querySelector('input[type=checkbox]').checked }",
            ":class": "{ 'table-primary': isRowSelected }",
        }

    def __init__(self, session=None, **kwargs):
        super().__init__(**kwargs)
        self.session = session

    @classmethod
    def get_select_column(cls, session, request, select_record_action, select_page_action):
        return SelectableHtmxColumn(
            session, request, select_record_action, select_page_action, accessor="case_id",
            attrs={
                'td__input': {
                    # `pageNumRecordsSelected` defined in template
                    "x-init": "if($el.checked) { pageNumRecordsSelected++; }",
                    "@click": (
                        "if ($el.checked !== isRowSelected) {"
                        # `numRecordsSelected` defined in template
                        "  $el.checked ? numRecordsSelected++ : numRecordsSelected--;"
                        # `pageNumRecordsSelected` defined in template
                        "  $el.checked ? pageNumRecordsSelected++ : pageNumRecordsSelected--; "
                        "} "
                        # `isRowSelected` defined in `row_attrs` in `class Meta`
                        "isRowSelected = $el.checked;"
                    ),
                },
                'th__input': {
                    # `pageNumRecordsSelected`, `pageTotalRecords`: defined in template
                    ":checked": "pageNumRecordsSelected == pageTotalRecords && pageTotalRecords > 0",
                },
            },
        )

    @classmethod
    def get_columns_from_session(cls, session):
        visible_columns = []
        for column_spec in session.columns.all():
            visible_columns.append(
                (column_spec.slug, EditableHtmxColumn(column_spec))
            )
        return visible_columns

    @property
    def is_read_only(self):
        return self.session.is_read_only

    @property
    @memoized
    def has_any_filtering(self):
        """
        Return whether any filtering is applied to the session.
        """
        return self.session.has_any_filtering

    @property
    @memoized
    def num_selected_records(self):
        """
        Return the number of selected records in the session.
        """
        return self.session.get_num_selected_records()

    @property
    @memoized
    def num_visible_selected_records(self):
        """
        Return the number of selected records visible with the current set of filters.
        """
        if self.has_any_filtering:
            return self.session.get_num_selected_records_in_queryset()
        return self.num_selected_records

    @property
    @memoized
    def has_changes(self):
        return self.session.has_changes()


class RecentCaseSessionsTable(BaseHtmxTable, tables.Table):

    class Meta(BaseHtmxTable.Meta):
        pass

    status = columns.TemplateColumn(
        template_name="data_cleaning/columns/task_status.html",
        verbose_name=gettext_lazy("Status"),
    )
    committed_on = columns.Column(
        verbose_name=gettext_lazy("Committed On"),
    )
    completed_on = columns.Column(
        verbose_name=gettext_lazy("Completed On"),
    )
    case_type = columns.Column(
        verbose_name=gettext_lazy("Case Type"),
    )
    case_count = columns.Column(
        verbose_name=gettext_lazy("# Cases Edited"),
    )
    form_ids = columns.TemplateColumn(
        template_name="data_cleaning/columns/task_form_ids.html",
        verbose_name=gettext_lazy("Form IDs"),
    )
    session_url = columns.TemplateColumn(
        template_name="data_cleaning/columns/task_session_url.html",
        verbose_name=gettext_lazy("Open Session"),
    )
