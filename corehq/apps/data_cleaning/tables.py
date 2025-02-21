from django.utils.translation import gettext_lazy
from django_tables2 import columns, tables

from corehq.apps.hqwebapp.tables.elasticsearch.records import CaseSearchElasticRecord
from corehq.apps.hqwebapp.tables.elasticsearch.tables import ElasticTable
from corehq.apps.hqwebapp.tables.htmx import BaseHtmxTable


class CleanCaseTable(BaseHtmxTable, ElasticTable):
    record_class = CaseSearchElasticRecord

    class Meta(BaseHtmxTable.Meta):
        pass

    name = columns.Column(
        verbose_name=gettext_lazy("Case Name"),
    )
    case_type = columns.Column(
        accessor="@case_type",
        verbose_name=gettext_lazy("Case Type"),
    )
    status = columns.Column(
        accessor="@status",
        verbose_name=gettext_lazy("Status"),
    )
    opened_on = columns.Column(
        verbose_name=gettext_lazy("Opened On"),
    )


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
