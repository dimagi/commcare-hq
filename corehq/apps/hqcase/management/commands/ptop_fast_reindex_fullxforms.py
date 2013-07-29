from datetime import datetime
import simplejson
from corehq.apps.hqcase.management.commands.ptop_fast_reindexer import PtopReindexer
from corehq.pillows.fullxform import FullXFormPillow
from couchforms.models import XFormInstance
from dimagi.utils.modules import to_function
from django.conf import settings


CHUNK_SIZE = 500
POOL_SIZE = 15


class Command(PtopReindexer):
    help = "Fast reindex of case elastic index by using the case view and reindexing cases"

    doc_class = XFormInstance
    view_name = 'hqadmin/domains_over_time'
    pillow_class = FullXFormPillow
    file_prefix = "ptop_fast_reindex_Full"

    def load_from_view(self):
        """
        Loads entire view, saves to file, set pillowtop checkpoint
        """
        dynamic_domains = FullXFormPillow.load_domains().keys()
        print "loaded full xform domains: %s" % dynamic_domains

        def full_view_iter():
            for domain in dynamic_domains:
                print "XForm View iter for domain: %s" % domain
                start_seq = 0
                startkey = [domain]
                endkey = [domain, {}]
                view_chunk = self.db.view(self.view_name, startkey=startkey, endkey=endkey, reduce=False, limit=self.chunk_size * self.chunk_size, skip=start_seq)
                while len(view_chunk) > 0:
                    for item in view_chunk:
                        yield item
                    start_seq += self.chunk_size * self.chunk_size
                    view_chunk = self.db.view(self.view_name, startkey=startkey, endkey=endkey, reduce=False, limit=CHUNK_SIZE * self.chunk_size, skip=start_seq)

        # Set pillowtop checkpoint for doc_class
        # though this might cause some superfluous reindexes of docs,
        # we're going to set the checkpoint BEFORE we start our operation so that any changes
        # that happen to cases while we're doing our reindexing would not get skipped once we
        # finish.

        current_db_seq = self.pillow.couch_db.info()['update_seq']
        self.pillow.set_checkpoint({'seq': current_db_seq})

        #Write sequence file to disk
        with open(self.get_seq_filename(), 'w') as fout:
            fout.write(str(current_db_seq))

        #load entire view to disk
        print "Getting full view list: %s" % datetime.utcnow().isoformat()
        with open(self.get_dump_filename(), 'w') as fout:
            fout.write("[")
            fout.write(','.join(simplejson.dumps(row) for row in full_view_iter()))
            fout.write("]")
        print "View and sequence written to disk: %s" % datetime.utcnow().isoformat()

    def custom_filter(self, view_row):
        """
        Custom filter if you want to do additional filtering based on the view

        Return true if to index, false if to SKIP
        """
        return view_row['key'] != 'http://code.javarosa.org/devicereport'
