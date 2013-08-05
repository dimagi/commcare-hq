from multiprocessing import Process, Queue, Pool
import sys
from django.core.management.base import BaseCommand, CommandError
from corehq.apps.domain.models import Domain
from dimagi.utils.couch.database import get_db, iter_docs
from corehq.apps.domainsync.config import DocumentTransform, save
from couchdbkit.client import Database
from optparse import make_option
from datetime import datetime

# doctypes we want to be careful not to copy, which must be explicitly
# specified with --include
DEFAULT_EXCLUDE_TYPES = [
    'ReportNotification',
    'WeeklyNotification',
    'DailyNotification'
]

NUM_PROCESSES = 8


class Command(BaseCommand):
    help = "Copies the contents of a domain to another database."
    args = '<sourcedb> <domain>'
    option_list = BaseCommand.option_list + (
        make_option('--include',
                    action='store',
                    dest='doc_types',
                    default='',
                    help='Comma-separated list of Document Types to copy'),
        make_option('--exclude',
                    action='store',
                    dest='doc_types_exclude',
                    default='',
                    help='Comma-separated list of Document Types to NOT copy.'),
        make_option('--since',
                    action='store',
                    dest='since',
                    default='',
                    help='Only copy documents newer than this date. Format: yyyy-MM-dd. Only '),
        make_option('--list-types',
                    action='store_true',
                    dest='list_types',
                    default=False,
                    help='Don\'t copy anything, just list all the available document types.'),
        make_option('--simulate',
                    action='store_true',
                    dest='simulate',
                    default=False,
                    help='Don\'t copy anything, print what would be copied.'),
    )

    def handle(self, *args, **options):
        if len(args) != 2:
            raise CommandError('Usage is copy_domain %s' % self.args)

        sourcedb = Database(args[0])
        domain = args[1].strip()
        simulate = options['simulate']

        since = datetime.strptime(options['since'], '%Y-%m-%d').isoformat() if options['since'] else None

        if options['list_types']:
            self.list_types(sourcedb, domain, since)
            sys.exit(0)

        if simulate:
            print "\nSimulated run, no data will be copied.\n"

        self.targetdb = get_db()

        domain_doc = Domain.get_by_name(domain)
        if domain_doc is None:
            self.copy_domain(sourcedb, domain)

        if options['doc_types']:
            doc_types = options['doc_types'].split(',')
            for type in doc_types:
                startkey = [x for x in [domain, type, since] if x is not None]
                endkey = [x for x in [domain, type, {}] if x is not None]
                self.copy_docs(sourcedb, domain, startkey, endkey, simulate, type=type, since=since)
        else:
            startkey = [domain]
            endkey = [domain, {}]
            exclude_types = DEFAULT_EXCLUDE_TYPES + options['doc_types_exclude'].split(',')
            self.copy_docs(sourcedb, domain, startkey, endkey, simulate, exclude_types=exclude_types)

    def list_types(self, sourcedb, domain, since):
        doc_types = sourcedb.view("domain/docs", startkey=[domain],
                                  endkey=[domain, {}], reduce=True, group=True, group_level=2)

        doc_count = dict([(row['key'][1], row['value']) for row in doc_types])
        if since:
            for doc_type in sorted(doc_count.iterkeys()):
                num_since = sourcedb.view("domain/docs", startkey=[domain, doc_type, since],
                                          endkey=[domain, doc_type, {}], reduce=True).all()
                num = num_since[0]['value'] if num_since else 0
                print "{:<30}- {:<6} total {}".format(doc_type, num, doc_count[doc_type])
        else:
            for doc_type in sorted(doc_count.iterkeys()):
                print "{:<30}- {}".format(doc_type, doc_count[doc_type])

    def copy_docs(self, sourcedb, domain, startkey, endkey, simulate, type=None, since=None, exclude_types=None):
        doc_ids = [result["id"] for result in sourcedb.view("domain/docs", startkey=startkey,
                                                            endkey=endkey, reduce=False)]

        total = len(doc_ids)
        count = 0
        msg = "Found %s matching documents in domain: %s" % (total, domain)
        msg += " of type: %s" % (type) if type else ""
        msg += " since: %s" % (since) if since else ""
        print msg

        queue = Queue(150)
        for i in range(NUM_PROCESSES):
            Worker(queue, sourcedb, self.targetdb, exclude_types, total, simulate).start()

        for doc in iter_docs(sourcedb, doc_ids, chunksize=100):
            count += 1
            queue.put((doc, count))

        # shutdown workers
        for i in range(NUM_PROCESSES):
            queue.put(None)

    def copy_domain(self, sourcedb, domain):
        print "Copying domain doc"
        result = sourcedb.view(
            "domain/domains",
            key=domain,
            reduce=False,
            include_docs=True
        ).first()

        if result and 'doc' in result:
            domain_doc = Domain.wrap(result['doc'])
            dt = DocumentTransform(domain_doc, sourcedb)
            save(dt, self.targetdb)
        else:
            print "Domain doc not found for domain %s." % domain


class Worker(Process):

    def __init__(self, queue, sourcedb, targetdb, exclude_types, total, simulate):
        super(Worker, self).__init__()
        self.queue = queue
        self.sourcedb = sourcedb
        self.targetdb = targetdb
        self.exclude_types = exclude_types
        self.total = total
        self.simulate = simulate

    def run(self):
        for doc, count in iter(self.queue.get, None):
            try:
                if self.exclude_types and doc["doc_type"] in self.exclude_types:
                    print "     SKIPPED (excluded type: %s). Synced %s/%s docs (%s: %s)" % \
                          (doc["doc_type"], count, self.total, doc["doc_type"], doc["_id"])
                else:
                    if not self.simulate:
                        dt = DocumentTransform(doc, self.sourcedb)
                        save(dt, self.targetdb)
                    print "     Synced %s/%s docs (%s: %s)" % (count, self.total, doc["doc_type"], doc["_id"])
            except Exception, e:
                print "     Document %s failed! Error is: %s" % (doc["_id"], e)
