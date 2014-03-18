from django.conf import settings

from casexml.apps.case.models import CommCareCase
from corehq.apps.hqcase.management.commands.ptop_fast_reindexer import ElasticReindexer
from corehq.pillows.reportcase import ReportCasePillow


class Command(ElasticReindexer):
    help = "Fast reindex of case elastic index by using the case view and reindexing cases"

    doc_class = CommCareCase
    view_name = 'hqcase/types_by_domain'
    pillow_class = ReportCasePillow
    file_prefix = "ptop_fast_reindex_Report"

    def full_couch_view_iter(self):
        view_kwargs = {}
        dynamic_domains = getattr(settings, 'ES_CASE_FULL_INDEX_DOMAINS', [])
        for domain in dynamic_domains:
            start_seq = 0
            view_kwargs["startkey"] = [domain]
            view_kwargs['endkey'] = [domain, {}]

            view_kwargs.update(self.get_extra_view_kwargs())
            view_chunk = self.db.view(
                self.view_name,
                reduce=False,
                limit=self.chunk_size * self.chunk_size,
                skip=start_seq,
                **view_kwargs
            )

            while len(view_chunk) > 0:
                for item in view_chunk:
                    yield item
                start_seq += self.chunk_size * self.chunk_size
                view_chunk = self.db.view(self.view_name,
                    reduce=False,
                    limit=self.chunk_size * self.chunk_size,
                    skip=start_seq,
                    **view_kwargs
                )
