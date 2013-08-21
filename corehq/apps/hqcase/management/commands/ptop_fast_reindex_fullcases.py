import simplejson
from casexml.apps.case.models import CommCareCase
from corehq.apps.hqcase.management.commands.ptop_fast_reindexer import PtopReindexer
from corehq.pillows.fullcase import FullCasePillow
from datetime import datetime
from django.conf import settings

CHUNK_SIZE = 500
POOL_SIZE = 15


class Command(PtopReindexer):
    help = "Fast reindex of case elastic index by using the case view and reindexing cases"

    doc_class = CommCareCase
    view_name = 'hqcase/types_by_domain'
    pillow_class = FullCasePillow
    file_prefix = "ptop_fast_reindex_Full"

    def full_couch_view_iter(self):
        start_seq = 0
        view_kwargs = {}
        dynamic_domains = getattr(settings, 'ES_CASE_FULL_INDEX_DOMAINS', [])
        for domain in dynamic_domains:
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
                view_chunk = self.db.view(self.view_name, reduce=False, limit=CHUNK_SIZE * self.chunk_size, skip=start_seq)


