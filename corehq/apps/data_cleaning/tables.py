from django.utils.translation import gettext_lazy
from django_tables2 import columns, tables

from corehq.apps.data_cleaning.columns import DataCleaningHtmxColumn
from corehq.apps.hqwebapp.tables.elasticsearch.records import CaseSearchElasticRecord
from corehq.apps.hqwebapp.tables.elasticsearch.tables import ElasticTable
from corehq.apps.hqwebapp.tables.htmx import BaseHtmxTable


class CleanCaseTable(BaseHtmxTable, ElasticTable):
    record_class = CaseSearchElasticRecord

    class Meta(BaseHtmxTable.Meta):
        pass

    @classmethod
    def get_columns_from_session(cls, session):
        visible_columns = []
        for column_spec in session.columns.all():
            slug = column_spec.prop_id.replace('@', '')
            visible_columns.append((slug, DataCleaningHtmxColumn(column_spec)))
        return visible_columns


class CaseCleaningTasksTable(BaseHtmxTable, tables.Table):

    class Meta(BaseHtmxTable.Meta):
        pass

    status = columns.Column(
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
    details = columns.Column(
        verbose_name=gettext_lazy("Details"),
    )
