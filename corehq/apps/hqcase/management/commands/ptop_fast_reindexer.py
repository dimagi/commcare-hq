from datetime import datetime
import time
from optparse import make_option
import sys

from django.core.management.base import NoArgsCommand
import simplejson

CHUNK_SIZE = 500
POOL_SIZE = 15

MAX_TRIES = 10
RETRY_DELAY = 60
RETRY_TIME_DELAY_FACTOR = 15



class FakeCouchDBLoader(object):
    """
    For the bulk fast reindexing - replace the traditional one couch GET per update
    and just do a bulk get of a cluster of ids. Rather than altering the pillow pipeline,
    just preload all docs of relevance into a dictionary and override the single couch.get_doc call.

    This needs to be patched after the initial bootstrap of the pillow which still needs to do
    couchy stuff.
    """
    docs = {}

    def open_doc(self, doc_id):
        return self.docs.get(doc_id, None)

    def save_doc(self):
        raise NotImplementedError("Wtf, this is a loader class")

    def fake_set_docs(self, doc_dict_by_id):
        """
        A non overriding method - fake set the docs in a dict so open_doc will get it like a regular couch database.
        """
        self.docs = doc_dict_by_id

class PtopReindexer(NoArgsCommand):
    help = "View based elastic reindexer"
    option_list = NoArgsCommand.option_list + (
        make_option('--resume',
                    action='store_true',
                    dest='resume',
                    default=False,
                    help='Resume, do not delete existing index data'),
        make_option('--bulk',
                    action='store_true',
                    dest='bulk',
                    default=False,
                    help='Do a bulk load'),
        make_option('--sequence',
                    type="int",
                    action='store',
                    dest='seq',
                    default=0,
                    help='Sequence id to resume from'),
        make_option('--noinput',
                    action='store_true',
                    dest='noinput',
                    default=False,
                    help='Skip important confirmation warnings?!?!'),
        make_option('--runfile',
                    action='store',
                    dest='runfile',
                    help='Previous run input file prefix',
                    default=None,),
        make_option('--chunk',
                    action='store',
                    type='int',
                    dest='chunk_size',
                    default=CHUNK_SIZE,
                    help='Previous run input file prefix',),
    )


    doc_class = None
    view_name = None
    couch_key = None
    pillow_class = None
    file_prefix = "ptop_fast_reindex_"



    def custom_filter(self, view_row):
        """
        Custom filter if you want to do additional filtering based on the view

        Return true if to index, false if to SKIP
        """
        return True

    def get_extra_view_kwargs(self):
        return {}

    def get_seq_prefix(self):
        if hasattr(self, '_seq_prefix'):
            datestring = self._seq_prefix
        else:
            datestring = datetime.now().strftime("%Y-%m-%d-%H%M")
            self._seq_prefix = datestring
        return datestring

    def set_seq_prefix(self, prefix):
        self._seq_prefix = prefix

    def get_seq_filename(self):
        #print "Run file prefix: ptop_fast_reindex_%s_%s" % (self.doc_class.__name__, datestring)
        seq_filename = "%s%s_%s_seq.txt" % (self.file_prefix, self.doc_class.__name__, self.get_seq_prefix())
        return seq_filename

    def get_dump_filename(self):
        view_dump_filename = "%s%s_%s_data.json" % (self.file_prefix, self.doc_class.__name__,  self.get_seq_prefix())
        return view_dump_filename

    def full_couch_view_iter(self):
        start_seq = 0
        view_kwargs = {}
        if self.couch_key is not None:
            view_kwargs["key"] = self.couch_key

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

    def load_from_view(self):
        """
        Loads entire view, saves to file, set pillowtop checkpoint
        """

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
            fout.write('\n'.join(simplejson.dumps(row) for row in self.full_couch_view_iter()))
        print "View and sequence written to disk: %s" % datetime.utcnow().isoformat()

    def load_seq_from_disk(self):
        """
        Main load of view data from disk.
        """
        print "Loading from disk: %s" % datetime.utcnow().isoformat()
        with open(self.get_seq_filename(), 'r') as fin:
            current_db_seq = fin.read()
            self.pillow.set_checkpoint({'seq': current_db_seq})

    def view_data_file_iter(self):
        with open(self.get_dump_filename(), 'r') as fin:
            for line in fin:
                yield simplejson.loads(line)

    def _bootstrap(self, options):
        self.resume = options['resume']
        self.bulk = options['bulk']
        self.pillow = self.pillow_class()
        self.db = self.doc_class.get_db()
        self.runfile = options['runfile']
        self.chunk_size = options.get('chunk_size', CHUNK_SIZE)
        self.start_num = options.get('seq', 0)


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

        self._bootstrap(options)
        start = datetime.utcnow()

        print "using chunk size %s" % self.chunk_size

        if not self.resume:
            #delete the existing index.
            print "Deleting index"
            self.pillow.delete_index()
            print "Recreating index"
            self.pillow.create_index()
            self.pillow.seen_types = {}
            self.load_from_view()
        else:
            if self.runfile is None:
                print "\tNeed a previous runfile prefix to access older snapshot of view. eg. ptop_fast_reindex_%s_yyyy-mm-dd-HHMM" % self.doc_class.__name__
                sys.exit()
            print "Starting fast tracked reindexing from view position %d" % self.start_num
            runparts = self.runfile.split('_')
            print runparts
            if len(runparts) != 5 or not self.runfile.startswith('ptop_fast_reindex'):
                print "\tError, runpart name must be in format ptop_fast_reindex_%s_yyyy-mm-dd-HHMM"
                sys.exit()

            self.set_seq_prefix(runparts[-1])
        seq = self.load_seq_from_disk()

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

    def process_row(self, row, count):
        if count > self.start_num:
            retries = 0
            while retries < MAX_TRIES:
                try:
                    if not self.custom_filter(row):
                        break
                    self.pillow.processor(row, do_set_checkpoint=False)
                    break
                except Exception, ex:
                    retries += 1
                    print "\tException sending single item %s, %s, retrying..." % (row['id'], ex)
                    time.sleep(RETRY_DELAY + retries * RETRY_TIME_DELAY_FACTOR)
        else:
            print "\tskipping... %d < %d" % (count, self.start_num)


    def load_traditional(self):
        for ix, item in enumerate(self.full_view_data):
            print "\tProcessing item %s (%d)" % (item['id'], ix)
            self.process_row(item, ix)

    def load_bulk(self):
        #chunk
        #if failure, try again
        curr_counter = 0
        start = self.start_num
        end = start + self.chunk_size

        #all couchy operations completed, faking out db now.

        json_iter = self.view_data_file_iter()

        bulk_slice = []
        self.pillow.couch_db = FakeCouchDBLoader()

        for curr_counter, json_doc in enumerate(json_iter):
            if curr_counter < start:
                continue
            if len(bulk_slice) == self.chunk_size:
                self.send_bulk(bulk_slice, start, end)
                bulk_slice = []
                start += self.chunk_size
                end += self.chunk_size
            else:
                bulk_slice.append(json_doc)
                continue

    def send_bulk(self, slice, start, end):
        doc_couch_db = self.pillow.document_class.get_db()
        doc_ids = [x['id'] for x in slice]
        slice_docs = doc_couch_db.all_docs(keys=doc_ids, include_docs=True)
        raw_doc_dict = dict((x['id'], x['doc']) for x in slice_docs.all())
        self.pillow.couch_db.fake_set_docs(raw_doc_dict) # update the fake couch instance's set of bulk loaded docs

        retries = 0
        bulk_start = datetime.utcnow()
        while retries < MAX_TRIES:
            try:
                self.pillow.process_bulk(slice)
                break
            except Exception, ex:
                retries += 1
                retry_time = (datetime.utcnow() - bulk_start).seconds + retries * RETRY_TIME_DELAY_FACTOR
                print "\t%s: Exception sending slice %d:%d, %s, retrying in %s seconds" % (datetime.now().isoformat(), start, end, ex, retry_time)
                time.sleep(retry_time)
                print "\t%s: Retrying again %d:%d..." % (datetime.now().isoformat(), start, end)
                bulk_start = datetime.utcnow() #reset timestamp when looping again






