from datetime import datetime
from django.core.management import CommandError
from corehq.apps.hqcase.management.commands.ptop_fast_reindexer import PtopReindexer
from dimagi.utils.modules import to_function
from fluff import FluffPillow
import gevent
import signal
from gevent.queue import Queue, Empty

CHUNK_SIZE = 500
POOL_SIZE = 15


class FluffPtopReindexer(PtopReindexer):
    help = "Fast reindex of fluff docs"

    view_name = 'domain/docs'

    # override these
    domain = None
    pillow_class = FluffPillow

    @property
    def doc_class(self):
        return self.pillow_class.document_class

    def get_extra_view_kwargs(self):
        return {
            'startkey': [self.domain, self.doc_class.__name__],
            'endkey': [self.domain, self.doc_class.__name__, {}],
        }

    def handle(self, *args, **options):
        if not options['noinput']:
            confirm = raw_input("""
        ### %s Fast Reindex !!! ###
        You have requested to do a fluff index reset via fast track.
        This will update all your fluff indicators in place.

        Type 'yes' to continue, or 'no' to cancel: """ % self.pillow_class.__name__)

            if confirm != 'yes':
                print "\tReset cancelled."
                return

        from gevent.monkey import patch_all
        patch_all()

        self._bootstrap(options)
        start = datetime.utcnow()

        gevent.signal(signal.SIGQUIT, gevent.shutdown)
        queue = Queue(POOL_SIZE)
        workers = [gevent.spawn(worker, self, queue) for i in range(POOL_SIZE)]

        print "Starting fast tracked reindexing"
        for i, row in enumerate(self.full_couch_view_iter()):
            queue.put((row, i))

        gevent.joinall(workers)

        end = datetime.utcnow()
        print "done in %s seconds" % (end - start).seconds


def worker(reindexer, queue):
    try:
        while True:
            row, count = queue.get(timeout=2)
            try:
                reindexer.process_row(row, count)
                print "\tProcessed item %s (%d)" % (row['id'], count)
            except Exception, e:
                print "\tRow %s failed! Error is: %s" % (row["_id"], e)
    except Empty:
        pass


class Command(FluffPtopReindexer):
    args = '<domain> <pillow_class>'

    def handle(self, *args, **options):
        if len(args) != 2:
            raise CommandError('Usage is ptop_fast_reindex_fluff %s' % self.args)

        self.domain = args[0]
        self.pillow_class = to_function(args[1])

        super(Command, self).handle(*args, **options)
