from multiprocessing import Process, Queue
import sys
import os
from couchdbkit import ResourceNotFound, ResourceConflict
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from http_parser.http import ParserError
from restkit import RequestError
from corehq.apps.domain.models import Domain
from corehq.apps.domainsync.management.commands.copy_utils import copy_postgres_data_for_docs
from corehq.util.dates import iso_string_to_date
from dimagi.utils.couch.database import get_db, iter_docs
from corehq.apps.domainsync.config import DocumentTransform, save
from couchdbkit.client import Database
from optparse import make_option
from corehq.util.soft_assert.api import soft_assert
_soft_assert = soft_assert('{}@{}'.format('tsheffels', 'dimagi.com')

# doctypes we want to be careful not to copy, which must be explicitly
# specified with --include
from dimagi.utils.parsing import json_format_date

DEFAULT_EXCLUDE_TYPES = [
    'ReportNotification',
    'WeeklyNotification',
    'DailyNotification'
]

NUM_PROCESSES = 8


class Command(BaseCommand):
    help = "Copies the contents of a domain to another database. " \
           "If tagetdb is not specified, the target is the database " \
           "specified by COUCH_DATABASE in your settings."
    args = '<sourcedb> <domain> [<targetdb>]'
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
        make_option('--exclude-attachments',
                    action='store_true',
                    dest='exclude_attachments',
                    default=False,
                    help="Don't copy document attachments, just the docs themselves."),
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
        make_option('--id-file',
                    action='store',
                    dest='id_file',
                    default='',
                    help="File containing one document ID per line. Only docs with these ID's will be copied"),
        make_option('--postgres-db',
                    action='store',
                    dest='postgres_db',
                    default='',
                    help="Name of postgres database to pull additional data from. This should map to a "
                         "key in settings.DATABASES. If not specified no additional postgres data will be "
                         "copied. This is currently used to pull CommCare Supply models."),
        make_option('--postgres-password',
                    action='store',
                    dest='postgres_password',
                    default='',
                    help="Password for postgres database to pull additional data from. If not specified will "
                         "default to the value in settings.DATABASES")
    )

    def handle(self, *args, **options):
        if len(args) not in [2, 3]:
            raise CommandError('Usage is copy_domain %s' % self.args)

        sourcedb = Database(args[0])
        domain = args[1].strip()
        simulate = options['simulate']
        exclude_attachments = options['exclude_attachments']

        since = json_format_date(iso_string_to_date(options['since'])) if options['since'] else None

        if options['list_types']:
            self.list_types(sourcedb, domain, since)
            sys.exit(0)

        if simulate:
            print "\nSimulated run, no data will be copied.\n"

        if options['postgres_db'] and options['postgres_password']:
            settings.DATABASES[options['postgres_db']]['PASSWORD'] = options['postgres_password']

        self.targetdb = Database(args[2]) if len(args) == 3 else get_db()

        try:
            domain_doc = Domain.get_by_name(domain)
        except ResourceNotFound:
            domain_doc = None

        if domain_doc is None:
            self.copy_domain(sourcedb, domain)

        if options['doc_types']:
            doc_types = options['doc_types'].split(',')
            for type in doc_types:
                startkey = [x for x in [domain, type, since] if x is not None]
                endkey = [x for x in [domain, type, {}] if x is not None]
                self.copy_docs(sourcedb, domain, simulate, startkey, endkey, type=type, since=since,
                               postgres_db=options['postgres_db'], exclude_attachments=exclude_attachments)
        elif options['id_file']:
            path = options['id_file']
            if not os.path.isfile(path):
                print "Path '%s' does not exist or is not a file" % path
                sys.exit(1)

            with open(path) as input:
                doc_ids = [line.rstrip('\n') for line in input]

            if not doc_ids:
                print "Path '%s' does not contain any document ID's" % path
                sys.exit(1)

            self.copy_docs(sourcedb, domain, simulate, doc_ids=doc_ids, postgres_db=options['postgres_db'],
                           exclude_attachments=exclude_attachments)
        else:
            startkey = [domain]
            endkey = [domain, {}]
            exclude_types = DEFAULT_EXCLUDE_TYPES + options['doc_types_exclude'].split(',')
            self.copy_docs(sourcedb, domain, simulate, startkey, endkey, exclude_types=exclude_types,
                           postgres_db=options['postgres_db'], exclude_attachments=exclude_attachments)

    def list_types(self, sourcedb, domain, since):
        doc_types = sourcedb.view("domain/docs", startkey=[domain],
                                  endkey=[domain, {}], reduce=True, group=True, group_level=2)

        doc_count = dict([(row['key'][1], row['value']) for row in doc_types])
        if since:
            for doc_type in sorted(doc_count.iterkeys()):
                num_since = sourcedb.view("domain/docs", startkey=[domain, doc_type, since],
                                          endkey=[domain, doc_type, {}], reduce=True).all()
                num = num_since[0]['value'] if num_since else 0
                print "{0:<30}- {1:<6} total {2}".format(doc_type, num, doc_count[doc_type])
        else:
            for doc_type in sorted(doc_count.iterkeys()):
                print "{0:<30}- {1}".format(doc_type, doc_count[doc_type])

    def copy_docs(self, sourcedb, domain, simulate, startkey=None, endkey=None, doc_ids=None,
                  type=None, since=None, exclude_types=None, postgres_db=None, exclude_attachments=False):

        if not doc_ids:
            doc_ids = [result["id"] for result in sourcedb.view("domain/docs", startkey=startkey,
                                                                endkey=endkey, reduce=False)]
        total = len(doc_ids)
        count = 0
        msg = "Found %s matching documents in domain: %s" % (total, domain)
        msg += " of type: %s" % (type) if type else ""
        msg += " since: %s" % (since) if since else ""
        print msg

        err_log = self._get_err_log()

        queue = Queue(150)
        for i in range(NUM_PROCESSES):
            Worker(queue, sourcedb, self.targetdb, exclude_types, total, simulate, err_log, exclude_attachments).start()

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

        if postgres_db:
            copy_postgres_data_for_docs(postgres_db, doc_ids=doc_ids, simulate=simulate)

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
            dt = DocumentTransform(domain_doc._obj, sourcedb)
            save(dt, self.targetdb)
        else:
            print "Domain doc not found for domain %s." % domain

    def _get_err_log(self):
        name = 'copy_domain.err.%s'
        for i in range(1000):  # arbitrarily large number
            candidate = name % i
            if not os.path.isfile(candidate):
                return open(candidate, 'a', buffering=1)


class Worker(Process):

    def __init__(self, queue, sourcedb, targetdb, exclude_types, total, simulate, err_log, exclude_attachments):
        super(Worker, self).__init__()
        self.queue = queue
        self.sourcedb = sourcedb
        self.targetdb = targetdb
        self.exclude_types = exclude_types
        self.exclude_attachments = exclude_attachments
        self.total = total
        self.simulate = simulate
        self.err_log = err_log

    def run(self):
        for doc, count in iter(self.queue.get, None):
            try:
                if self.exclude_types and doc["doc_type"] in self.exclude_types:
                    print "     SKIPPED (excluded type: %s). Synced %s/%s docs (%s: %s)" % \
                          (doc["doc_type"], count, self.total, doc["doc_type"], doc["_id"])
                else:
                    if not self.simulate:
                        for i in reversed(range(5)):
                            try:
                                dt = DocumentTransform(doc, self.sourcedb, self.exclude_attachments)
                                break
                            except RequestError as r:
                                if i == 0:
                                    _soft_assert(False, 'Copy domain failed after 5 tries with {}'.format(r))
                                    raise
                        for i in reversed(range(5)):
                            try:
                                save(dt, self.targetdb)
                            except (ResourceConflict, ParserError, TypeError) as e:
                                if i == 0:
                                    _soft_assert(False, 'Copy domain failed after 5 tries with {}'.format(e))
                                    raise
                    print "     Synced %s/%s docs (%s: %s)" % (count, self.total, doc["doc_type"], doc["_id"])
            except Exception, e:
                self.err_log.write('%s\n' % doc["_id"])
                print "     Document %s failed! Error is: %s %s" % (doc["_id"], e.__class__.__name__, e)
