from django.conf import settings

from casexml.apps.case.models import CommCareCase
from corehq.apps.hqcase.management.commands.ptop_fast_reindexer import ElasticReindexer
from corehq.pillows.reportcase import ReportCasePillow


class Command(ElasticReindexer):
    help = "Fast reindex of case elastic index by using the case view and reindexing cases"

    doc_class = CommCareCase
    view_name = 'cases_by_owner/view'
    pillow_class = ReportCasePillow
    file_prefix = "ptop_fast_reindex_Report"

    def full_couch_view_iter(self):
        view_kwargs = self.get_extra_view_kwargs()
        dynamic_domains = getattr(settings, 'ES_CASE_FULL_INDEX_DOMAINS', [])
        for domain in dynamic_domains:
            rows = self.paginate_view(
                self.db,
                self.view_name,
                reduce=False,
                startkey=[domain],
                endkey=[domain, {}],
                **view_kwargs
            )
            for row in rows:
                yield row
