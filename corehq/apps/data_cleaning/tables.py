from django.utils.translation import gettext_lazy
from django_tables2 import columns, tables

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
        for col in session.columns.all():
            slug = col.prop_id.replace('@', '')
            visible_columns.append((
                slug, columns.Column(
                    verbose_name=col.label,
                    accessor=col.prop_id,
                )
            ))
        return visible_columns


class CaseCleaningTasksTable(BaseHtmxTable, tables.Table):

    class Meta(BaseHtmxTable.Meta):
        pass

    status = columns.Column(
        verbose_name=gettext_lazy("Status"),
    )
    time = columns.Column(
        verbose_name=gettext_lazy("Time"),
    )
    case_type = columns.Column(
        verbose_name=gettext_lazy("Case Type"),
    )
    details = columns.Column(
        verbose_name=gettext_lazy("Details"),
    )
