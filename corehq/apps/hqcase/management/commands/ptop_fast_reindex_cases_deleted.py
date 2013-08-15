from casexml.apps.case.models import CommCareCase
from corehq.apps.hqcase.management.commands.ptop_fast_reindexer import PtopReindexer, MAX_TRIES, RETRY_DELAY, RETRY_TIME_DELAY_FACTOR
from corehq.pillows.case import CasePillow
from datetime import datetime
import time
from optparse import make_option
import sys

from django.core.management.base import NoArgsCommand
import simplejson


CHUNK_SIZE = 500
POOL_SIZE = 15


class Command(PtopReindexer):
    help = "one off Fast reindex of case elastic index by using the view of deleted cases"

    doc_class = CommCareCase
    view_name = 'users/deleted_cases_by_user'
    pillow_class = CasePillow


    def handle(self, *args, **options):
        if not options['noinput']:
            confirm = raw_input("""
        ### %s Fast Reindex !!! ###
        You have requested to do an elastic index reset via fast track.
        This will IRREVERSIBLY REMOVE
        ALL index data in the case index and will take a while to reload.
        Are you sure you want to do this. Also you MUST have run_ptop disabled for this to run.

        Type 'yes' to continue, or 'no' to cancel: """ % self.doc_class.__name__)

            if confirm != 'yes':
                print "\tReset cancelled."
                return

            confirm_ptop = raw_input("""\tAre you sure you disabled run_ptop? """)
            if confirm_ptop != "yes":
                return

            confirm_alias = raw_input("""\tAre you sure you are not blowing away a production index? """)
            if confirm_alias != "yes":
                return

        start = datetime.utcnow()
        self.resume = options['resume']
        self.bulk = options['bulk']
        self.pillow = self.pillow_class()
        self.db = self.doc_class.get_db()
        self.runfile = options['runfile']
        self.chunk_size = options.get('chunk_size', CHUNK_SIZE)
        self.start_num = options.get('seq', 0)

        print "using chunk size %s" % self.chunk_size

        if not self.resume:
            #delete the existing index.
            print "Not Deleting index, this is just a one off command"
            #self.pillow.delete_index()
            #print "Recreating index"
            #self.pillow.create_index()
            #self.pillow.seen_types = {}
            self.load_from_view()
        else:
            if self.runfile is None:
                print "\tNeed a previous runfile prefix to access older snapshot of view. eg. ptop_fast_reindex_%s_yyyy-mm-dd-HHMM" % self.doc_class.__name__
                sys.exit()
            print "Starting fast tracked reindexing from view position %d" % self.start_num
            runparts = self.runfile.split('_')
            print runparts
            if len(runparts) != 5 or not self.runfile.startswith('ptop_fast_reindex') or runparts[3] != self.doc_class.__name__:
                print "\tError, runpart name must be in format ptop_fast_reindex_%s_yyyy-mm-dd-HHMM"
                sys.exit()

            self.set_seq_prefix(runparts[-1])
        self.load_from_disk()

        #configure index to indexing mode
        self.pillow.set_index_reindex_settings()

        if self.bulk:
            print "Preparing Bulk Payload"
            self.load_bulk()
        else:
            print "Loading traditional method"
            self.load_traditional()
        end = datetime.utcnow()

        print "setting index settings to normal search configuration"
        self.pillow.set_index_normal_settings()
        print "done in %s seconds" % (end - start).seconds

    def load_traditional(self):
        total_length = len(self.full_view_data)
        for ix, item in enumerate(self.full_view_data):
            if ix < self.start_num:
                print "\tskipping... %d < %d" % (ix, self.start_num)
                continue
            load_start = datetime.utcnow()
            retries = 0
            while retries < MAX_TRIES:
                try:
                    if not self.custom_filter(item):
                        break
                    print "\tProcessing item %s (%d/%d)" % (item['id'], ix, total_length)
                    self.pillow.processor(item, do_set_checkpoint=False)
                    break
                except Exception, ex:
                    retries += 1
                    print "\tException sending single item %s, %s, retrying..." % (item['id'], ex)
                    load_end = datetime.utcnow()
                    time.sleep(RETRY_DELAY + retries * RETRY_TIME_DELAY_FACTOR)

