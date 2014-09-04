import os
from optparse import make_option
from multiprocessing import Process, Queue

from django.core.management.base import BaseCommand, CommandError

from corehq.apps.domain.models import Domain
from corehq.apps.domainsync.config import DocumentTransform
from dimagi.utils.couch.database import get_db, iter_docs

NUM_PROCESSES = 8

# This management command is closely modeled after copy_domain. It would be
# nice to reduce the code reuse.

class Command(BaseCommand):
    help = "Deletes the contents of a domain"
    args = '<domain>'

    option_list = BaseCommand.option_list + (
        make_option('--simulate',
                    action='store_true',
                    dest='simulate',
                    default=False,
                    help='Don\'t delete anything, print what would be deleted.'),
    )

    def handle(self, *args, **options):
        if len(args) != 1:
            raise CommandError('Usage is delete_domain %s' % self.args)

        sourcedb = get_db()
        domain = args[0].strip()
        simulate = options['simulate']

        if simulate:
            print "\nSimulated run, no data will be deleted.\n"

        domain_doc = Domain.get_by_name(domain)
        if domain_doc is None:
            # If this block not entered, domain will be deleted in delete_docs
            self.delete_domain(sourcedb, domain, simulate)
            

        startkey = [domain]
        endkey = [domain, {}]
        self.delete_docs(sourcedb, domain, simulate, startkey, endkey)

    def delete_domain(self, sourcedb, domain, simulate):

        result = sourcedb.view(
            "domain/domains",
            key=domain,
            reduce=False,
            include_docs=True
        ).first()

        if result and 'doc' in result:
            if not simulate:
                print "Deleting domain doc"
                domain_doc = Domain.wrap(result['doc'])
                sourcedb.delte_doc(domain_doc) #TODO: Attachements are deleted by this as well, right?
        else:
            print "Domain doc not found for domain %s." % domain

    def delete_docs(self, sourcedb, domain, simulate, startkey, endkey):
        # TODO: What will happen to documents in multiple domains?

        doc_ids = [ result["id"] for result in sourcedb.view("domain/docs",
                                                    startkey=startkey,
                                                    endkey=endkey,
                                                    reduce=False
                                                )]
        total = len(doc_ids)
        count = 0
        msg = "Found %s matching documents in domain: %s" % (total, domain)
        print msg

        err_log = self._get_err_log()

        queue = Queue(150)
        for i in range(NUM_PROCESSES):
            Worker(queue, sourcedb, total, simulate, err_log).start()

        for doc in iter_docs(sourcedb, doc_ids, chunksize=100):
            count += 1
            queue.put((doc, count))

        # shutdown workers
        for i in range(NUM_PROCESSES):
            queue.put(None)

        err_log.close()
        if os.stat(err_log.name)[6] == 0:
            os.remove(err_log.name)
        else:
            print 'Failed document IDs written to %s' % err_log.name

    def _get_err_log(self):
        name = 'copy_domain.err.%s'
        for i in range(1000):  # arbitrarily large number
            candidate = name % i
            if not os.path.isfile(candidate):
                return open(candidate, 'a', buffering=1)

class Worker(Process):

    def __init__(self, queue, sourcedb, total, simulate, err_log):
        super(Worker, self).__init__()
        self.queue = queue
        self.sourcedb = sourcedb
        self.total = total
        self.simulate = simulate
        self.err_log = err_log

    def run(self):
        for doc, count in iter(self.queue.get, None):
            try:
                if not self.simulate:
                    dt = DocumentTransform(doc, self.sourcedb)
                    self.sourcedb.delete_doc(doc) #TODO: This deletes attachements too, right?
                print "     Deleted %s/%s docs (%s: %s)" % (count, self.total, doc["doc_type"], doc["_id"])
            except Exception, e:
                self.err_log.write('%s\n' % doc["_id"])
                print "     Document %s failed! Error is: %s" % (doc["_id"], e)