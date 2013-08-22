from corehq.apps.hqcase.management.commands.ptop_fast_reindexer import PtopReindexer
from corehq.pillows.fullxform import FullXFormPillow
from couchforms.models import XFormInstance


#TO BE DEPRECATED
class Command(PtopReindexer):
    help = "Fast reindex of case elastic index by using the case view and reindexing cases"

    doc_class = XFormInstance
    view_name = 'hqadmin/domains_over_time'
    pillow_class = FullXFormPillow
    file_prefix = "ptop_fast_reindex_Full"


    def full_couch_view_iter(self):
        view_kwargs = {}
        dynamic_domains = FullXFormPillow.load_domains().keys()
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

        if 'doc' in view_row:
            return view_row['doc']['xmlns'] != 'http://code.javarosa.org/devicereport'
        else:
            return view_row['key'] != 'http://code.javarosa.org/devicereport'

