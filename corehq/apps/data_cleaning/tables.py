import json
from memoized import memoized

from django.utils.translation import gettext_lazy
from django_tables2 import columns, tables

from corehq.apps.data_cleaning.columns import (
    DataCleaningHtmxColumn,
    DataCleaningHtmxSelectionColumn,
)
from corehq.apps.data_cleaning.models import (
    BULK_OPERATION_CHUNK_SIZE,
    MAX_RECORDED_LIMIT,
    MAX_SESSION_CHANGES,
)
from corehq.apps.data_cleaning.records import EditableCaseSearchElasticRecord
from corehq.apps.hqwebapp.tables.elasticsearch.tables import ElasticTable
from corehq.apps.hqwebapp.tables.htmx import BaseHtmxTable


class CleanCaseTable(BaseHtmxTable, ElasticTable):
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
        return DataCleaningHtmxSelectionColumn(
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
                (column_spec.slug, DataCleaningHtmxColumn(column_spec))
            )
        return visible_columns

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
    def num_edited_records(self):
        """
        Return the number of edited records in the session.
        """
        return self.change_counts["num_records_edited"]

    @property
    @memoized
    def change_counts(self):
        """
        A dictionary of "change_counts" for the session.
        This includes the number of records edited and the number of records
        that have reached the maximum number of changes.
        The keys are:
            - num_records_edited: the number of records edited
            - num_records_at_max_changes: the number of records that have reached the maximum number of changes
        """
        return self.session.get_change_counts()

    @staticmethod
    def get_edit_details(session, change_counts=None):
        """
        Return a dictionary of edit details for the Alpine.store.
        This includes the number of records edited and the number of records
        that have reached the maximum number of changes.

        This is a staticmethod so that the TableHostView can also call this.

        `change_counts` is optional and will be fetched from the session if not provided,
        it allows us to memoize the change_counts for additional references in the table's template.

        The keys are:
            - numRecordsEdited: the number of records edited
            - numRecordsOverLimit: the number of records that have reached the maximum number of changes
            - isSessionAtChangeLimit: whether the session has reached the maximum number of changes
        """
        change_counts = change_counts or session.get_change_counts()
        return {
            "numRecordsEdited": change_counts["num_records_edited"],
            "numRecordsOverLimit": change_counts["num_records_at_max_changes"],
            "isSessionAtChangeLimit": session.get_num_changes() >= MAX_SESSION_CHANGES,
            "isUndoMultiple": session.is_undo_multiple(),
        }

    @property
    @memoized
    def edit_details(self):
        """
        Return a JSON dump of the result of get_edit_details.
        This is used to pass the edit details to the Alpine store.
        This is a property so that it can be memoized and used in the template.
        """
        return json.dumps(self.get_edit_details(self.session, self.change_counts))


class CaseCleaningTasksTable(BaseHtmxTable, tables.Table):

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
        verbose_name=gettext_lazy("# Cases Cleaned"),
    )
    form_ids = columns.TemplateColumn(
        template_name="data_cleaning/columns/task_form_ids.html",
        verbose_name=gettext_lazy("Form IDs"),
    )
