from datetime import datetime
import time
from optparse import make_option
import sys

from django.core.management.base import NoArgsCommand
import json
from corehq.util.couch_helpers import paginate_view
from pillowtop.couchdb import CachedCouchDB
from pillowtop.es_utils import set_index_reindex_settings, set_index_normal_settings, create_index_for_pillow, \
    initialize_mapping_if_necessary
from pillowtop.feed.couch import change_from_couch_row
from pillowtop.feed.interface import Change
from pillowtop.listener import AliasedElasticPillow, PythonPillow
from pillowtop.pillow.interface import PillowRuntimeContext

CHUNK_SIZE = 10000
POOL_SIZE = 15

MAX_TRIES = 10
RETRY_DELAY = 60
RETRY_TIME_DELAY_FACTOR = 15


class PaginateViewLogHandler(object):
    def __init__(self, reindexer):
        self.reindexer = reindexer

    def log(self, *args, **kwargs):
        self.reindexer.log(*args, **kwargs)

    def view_starting(self, db, view_name, kwargs, total_emitted):
        self.log('Fetching rows {}-{} from couch'.format(
            total_emitted,
            total_emitted + kwargs['limit'] - 1)
        )
        startkey = kwargs.get('startkey')
        self.log(u'  startkey={!r}, startkey_docid={!r}'.format(startkey, kwargs.get('startkey_docid')))

    def view_ending(self, db, view_name, kwargs, total_emitted, time):
        self.log('View call took {}'.format(time))


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
        make_option('--in-place',
                    action='store_true',
                    dest='in_place',
                    default=False,
                    help='Run the reindex in place - assuming it is against a live index.'),
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
                    help='Skip important confirmation warnings.'),
        make_option('--runfile',
                    action='store',
                    dest='runfile',
                    help='Previous run input file prefix',
                    default=None,),
        make_option('--chunk',
                    action='store',
                    type='int',
                    dest='chunk_size',
                    help='Number of docs to save at a time',),
    )

    doc_class = None
    view_name = None
    couch_key = None
    pillow_class = None  # the pillow where the main indexing logic is
    # the pillow that points to the index you want to index.
    # By default this == self.pillow_class
    indexing_pillow_class = None
    file_prefix = "ptop_fast_reindex_"
    default_chunk_size = CHUNK_SIZE

    def __init__(self):
        super(PtopReindexer, self).__init__()
        if not getattr(self, "indexing_pillow_class", None):
            self.indexing_pillow_class = self.pillow_class

    def log(self, message):
        print '[{}] {}'.format(self.__module__.split('.')[-1], message)

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
            datestring = datetime.utcnow().strftime("%Y-%m-%d-%H%M")
            self._seq_prefix = datestring
        return datestring

    def set_seq_prefix(self, prefix):
        self._seq_prefix = prefix

    def get_seq_filename(self):
        seq_filename = "%s%s_%s_seq.txt" % (self.file_prefix, self.pillow_class.__name__, self.get_seq_prefix())
        return seq_filename

    def get_dump_filename(self):
        view_dump_filename = "%s%s_%s_data.json" % (self.file_prefix, self.pillow_class.__name__,  self.get_seq_prefix())
        return view_dump_filename

    def paginate_view(self, *args, **kwargs):
        if 'chunk_size' not in kwargs:
            kwargs['chunk_size'] = self.chunk_size
        if 'log_handler' not in kwargs:
            kwargs['log_handler'] = PaginateViewLogHandler(self)
        return paginate_view(*args, **kwargs)

    def full_couch_view_iter(self):
        if hasattr(self.pillow, 'include_docs_when_preindexing'):
            include_docs = self.pillow.include_docs_when_preindexing
        else:
            include_docs = self.pillow.include_docs
        view_kwargs = {"include_docs": include_docs}
        if self.couch_key is not None:
            view_kwargs["key"] = self.couch_key

        view_kwargs.update(self.get_extra_view_kwargs())

        return self.paginate_view(
            self.db,
            self.view_name,
            reduce=False,
            **view_kwargs
        )

    def load_from_view(self):
        """
        Loads entire view, saves to file, set pillowtop checkpoint
        """
        # Set pillowtop checkpoint for doc_class
        # though this might cause some superfluous reindexes of docs,
        # we're going to set the checkpoint BEFORE we start our operation so that any changes
        # that happen to cases while we're doing our reindexing would not get skipped once we
        # finish.

        current_db_seq = self.pillow.get_couch_db().info()['update_seq']

        # Write sequence file to disk
        seq_filename = self.get_seq_filename()
        self.log('Writing sequence file to disk: {}'.format(seq_filename))
        with open(seq_filename, 'w') as fout:
            fout.write(str(current_db_seq))

        # Load entire view to disk
        dump_filename = self.get_dump_filename()
        self.log('Writing dump file to disk: {}, starting at {}'.format(
            dump_filename, datetime.utcnow().isoformat()))
        with open(dump_filename, 'w') as fout:
            for row in self.full_couch_view_iter():
                fout.write('{}\n'.format(json.dumps(row)))
        self.log("View and sequence written to disk: %s" % datetime.utcnow().isoformat())

    def _load_seq_from_disk(self):
        self.log("Loading from disk: %s" % datetime.utcnow().isoformat())
        with open(self.get_seq_filename(), 'r') as fin:
            return fin.read()

    def view_data_file_iter(self, start=0):
        with open(self.get_dump_filename(), 'r') as fin:
            for line_count, line in enumerate(fin):
                if line_count < start:
                    continue
                yield json.loads(line)

    def _bootstrap(self, options):
        self.resume = options['resume']
        self.pillow = self.pillow_class()
        self.bulk = options['bulk'] and isinstance(self.pillow, AliasedElasticPillow)
        self.indexing_pillow = self.indexing_pillow_class()
        self.db = self.doc_class.get_db()
        self.runfile = options['runfile']
        self.chunk_size = options.get('chunk_size', None) or self.default_chunk_size
        self.start_num = options.get('seq', 0)
        self.in_place = options['in_place']

    def handle(self, *args, **options):
        if not options['noinput'] and not _ask_user_to_proceed(self.indexing_pillow_class.__name__):
            self.log("\tReset cancelled by user.")
            return

        self._bootstrap(options)
        start = datetime.utcnow()
        self.log("using chunk size %s" % self.chunk_size)

        if not self.resume:
            self.pre_load_hook()
            self.load_from_view()
        else:
            if self.runfile is None:
                self.log("\tNeed a previous runfile prefix to access older snapshot of view. eg. ptop_fast_reindex_%s_yyyy-mm-dd-HHMM" % self.pillow_class.__name__)
                sys.exit()
            self.log("Starting fast tracked reindexing from view position %d" % self.start_num)
            runparts = self.runfile.split('_')
            self.log(runparts)
            if len(runparts) != 5 or not self.runfile.startswith('ptop_fast_reindex'):
                self.log("\tError, runpart name must be in format ptop_fast_reindex_%s_yyyy-mm-dd-HHMM")
                sys.exit()

            self.set_seq_prefix(runparts[-1])

        if not self.in_place:
            seq = self._load_seq_from_disk()
            self.pillow.set_checkpoint({'seq': seq})

        self.post_load_hook()
        self.pillow.set_couch_db(
            CachedCouchDB(self.pillow.document_class.get_db().uri, readonly=True)
        )
        if self.bulk:
            self.log("Preparing Bulk Payload")
            self.load_bulk()
        else:
            self.log("Loading traditional method")
            self.load_traditional()
        end = datetime.utcnow()
        self.finish_saving()
        self.pre_complete_hook()
        self.log("done in %s seconds" % (end - start).seconds)

    def process_row(self, row, count):
        if count >= self.start_num:
            retries = 0
            while retries < MAX_TRIES:
                try:
                    if not self.custom_filter(row):
                        break
                    if not isinstance(row, Change):
                        assert isinstance(row, dict)
                        row = change_from_couch_row(row)
                    self.pillow.processor(row, PillowRuntimeContext(do_set_checkpoint=False))
                    break
                except Exception, ex:
                    retries += 1
                    self.log("\tException sending single item %s, %s, retrying..." % (row['id'], ex))
                    time.sleep(RETRY_DELAY + retries * RETRY_TIME_DELAY_FACTOR)
        else:
            self.log("\tskipping... %d < %d" % (count, self.start_num))

    def load_traditional(self):
        """
        Iterative view indexing - use --bulk for faster reindex.
        :return:
        """
        for ix, item in enumerate(self.view_data_file_iter()):
            self.log("\tProcessing item %s (%d)" % (item['id'], ix))
            self.process_row(item, ix)

    def load_bulk(self):
        start = self.start_num
        end = start + self.chunk_size

        json_iter = self.view_data_file_iter(start)

        bulk_slice = []
        for json_doc in json_iter:
            bulk_slice.append(json_doc)
            if len(bulk_slice) == self.chunk_size:
                self.send_bulk(bulk_slice, start, end)
                bulk_slice = []
                start += self.chunk_size
                end += self.chunk_size

        self.send_bulk(bulk_slice, start, end)

    def finish_saving(self):
        # python pillows may have some chunked up changes so make sure they get processed
        if isinstance(self.pillow, PythonPillow) and self.pillow.use_chunking:
            self.pillow.process_chunk()

    def send_bulk(self, slice, start, end):
        doc_ids = [x['id'] for x in slice]
        self.pillow.get_couch_db().bulk_load(doc_ids, purge_existing=True)
        filtered_ids = set([d['_id'] for d in filter(self.custom_filter, self.pillow.get_couch_db().get_all())])
        filtered_slice = filter(lambda change: change['id'] in filtered_ids, slice)

        retries = 0
        bulk_start = datetime.utcnow()
        while retries < MAX_TRIES:
            try:
                self.log('Sending chunk to ES')
                assert isinstance(self.pillow, AliasedElasticPillow)
                self.pillow.process_bulk(filtered_slice)
                break
            except Exception as ex:
                retries += 1
                retry_time = (datetime.utcnow() - bulk_start).seconds + retries * RETRY_TIME_DELAY_FACTOR
                self.log("\t%s: Exception sending slice %d:%d, %s, retrying in %s seconds" % (datetime.utcnow().isoformat(), start, end, ex, retry_time))
                time.sleep(retry_time)
                self.log("\t%s: Retrying again %d:%d..." % (datetime.utcnow().isoformat(), start, end))
                # reset timestamp when looping again
                bulk_start = datetime.utcnow()

    def pre_load_hook(self):
        pass

    def post_load_hook(self):
        pass

    def pre_complete_hook(self):
        pass


def _ask_user_to_proceed(pillow_name):
    confirm = raw_input("""
        ### %s Fast Reindex !!! ###

        You have requested to do an elastic index reset via fast track.
        This will IRREVERSIBLY REMOVE ALL index data in the associated index.
        Also, you MUST have run_ptop disabled for this to run.

        Are you sure you want to do this?

        Type 'yes' to continue, or 'no' to cancel: """ % pillow_name)

    if confirm != 'yes':
        return False

    confirm_ptop = raw_input("""\tAre you sure you disabled run_ptop? """)
    if confirm_ptop != "yes":
        return False

    confirm_alias = raw_input("""\tAre you sure you are not blowing away a production index? """)
    if confirm_alias != "yes":
        return False
    return True


class ElasticReindexer(PtopReindexer):

    own_index_exists = True

    def pre_load_hook(self):
        if not self.in_place and self.own_index_exists:
            # delete the existing index.
            self.log("Deleting index")
            self.indexing_pillow.get_es_new().indices.delete(self.indexing_pillow.es_index)
            self.log("Recreating index")
            create_index_for_pillow(self.indexing_pillow)
            initialize_mapping_if_necessary(self.indexing_pillow)

    def post_load_hook(self):
        if not self.in_place:
            # configure index to indexing mode
            set_index_reindex_settings(self.indexing_pillow.get_es_new(), self.indexing_pillow.es_index)

    def pre_complete_hook(self):
        if not self.in_place:
            self.log("setting index settings to normal search configuration and refreshing index")
            set_index_normal_settings(self.indexing_pillow.get_es_new(), self.indexing_pillow.es_index)
        # refresh the index
        self.indexing_pillow.get_es_new().indices.refresh(self.indexing_pillow.es_index)
