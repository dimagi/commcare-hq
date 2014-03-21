from corehq.apps.hqcase.management.commands.ptop_fast_reindexer import ElasticReindexer
from corehq.pillows.reportxform import ReportXFormPillow
from couchforms.models import XFormInstance
from django.conf import settings


class Command(ElasticReindexer):
    help = "Fast reindex of case elastic index by using the case view and reindexing cases"

    doc_class = XFormInstance
    view_name = 'hqadmin/domains_over_time'
    pillow_class = ReportXFormPillow
    file_prefix = "ptop_fast_reindex_Report"


    def full_couch_view_iter(self):
        view_kwargs = {}
        dynamic_domains = getattr(settings, 'ES_XFORM_FULL_INDEX_DOMAINS', [])
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

    def custom_filter(self, view_row):
        """
        Custom filter if you want to do additional filtering based on the view

        Return true if to index, false if to SKIP
        """
        if 'xmlns' in view_row:
            return view_row['xmlns'] != 'http://code.javarosa.org/devicereport'
        elif 'key' in view_row:
            return view_row['key'] != 'http://code.javarosa.org/devicereport'
        else:
            return True



