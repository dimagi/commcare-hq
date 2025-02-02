from django.utils.translation import gettext_lazy
from django_tables2 import columns

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
