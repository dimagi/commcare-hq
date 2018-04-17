from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from multiprocessing import Process, Queue
import sys
import os
from six.moves.urllib.parse import urlparse
from couchdbkit import ResourceNotFound, ResourceConflict
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from http_parser.http import ParserError
from restkit import RequestError
from corehq.apps.domain.models import Domain
from corehq.apps.domainsync.management.commands.copy_utils import copy_postgres_data_for_docs
from corehq.util.couchdb_management import CouchConfig
from corehq.util.dates import iso_string_to_date
from dimagi.utils.couch.database import iter_docs
from corehq.apps.domainsync.config import DocumentTransform, save

# doctypes we want to be careful not to copy, which must be explicitly
# specified with --include
from dimagi.utils.parsing import json_format_date
from six.moves import range
import six

DEFAULT_EXCLUDE_TYPES = [
    'ReportNotification',
    'WeeklyNotification',
    'DailyNotification'
]

NUM_PROCESSES = 8


class Command(BaseCommand):
    """
    DEPRECATED/NEEDS WORK - `copy_domain` is basically broken because of
      - attachments in blobdb
      - SQL data.

    Scale trello card to update this: https://trello.com/c/OGGrmoGI/16-copydomain

    """
    help = "Copies the contents of a domain to another database. " \
           "If targetdb is not specified, the target is the database " \
           "specified by COUCH_DATABASE in your settings."

    def add_arguments(self, parser):
        parser.add_argument(
            'sourcedb',
        )
        parser.add_argument(
            'domain',
        )
        parser.add_argument(
            'targetdb',
            nargs='?',
        )
        parser.add_argument(
            '--include',
            action='store',
            dest='doc_types',
            default='',
            help='Comma-separated list of Document Types to copy',
        )
        parser.add_argument(
            '--exclude',
            action='store',
            dest='doc_types_exclude',
            default='',
            help='Comma-separated list of Document Types to NOT copy.',
        )
        parser.add_argument(
            '--exclude-attachments',
            action='store_true',
            dest='exclude_attachments',
            default=False,
            help="Don't copy document attachments, just the docs themselves.",
        )
        parser.add_argument(
            '--since',
            action='store',
            dest='since',
            default='',
            help='Only copy documents newer than this date. Format: yyyy-MM-dd. Only ',
        )
        parser.add_argument(
            '--list-types',
            action='store_true',
            dest='list_types',
            default=False,
            help='Don\'t copy anything, just list all the available document types.',
        )
        parser.add_argument(
            '--simulate',
            action='store_true',
            dest='simulate',
            default=False,
            help='Don\'t copy anything, print what would be copied.',
        )
        parser.add_argument(
            '--id-file',
            action='store',
            dest='id_file',
            default='',
            help="File containing one document ID per line. Only docs with these ID's will be copied",
        )
        parser.add_argument(
            '--postgres-db',
            action='store',
            dest='postgres_db',
            default='',
            help="Name of postgres database to pull additional data from. This should map to a "
                 "key in settings.DATABASES. If not specified no additional postgres data will be "
                 "copied. This is currently used to pull CommCare Supply models.",
        )
        parser.add_argument(
            '--postgres-password',
            action='store',
            dest='postgres_password',
            default='',
            help="Password for postgres database to pull additional data from. If not specified will "
                 "default to the value in settings.DATABASES",
        )
        parser.add_argument(
            '--dont-run-multi-process',
            action='store_false',
            dest='run_multi_process',
            default=True,
            help="If set to true this spawn multiple processes which should speed up the time taken to "
                 "copy. This must be false if running in a supervised process",
        )

    def iter_source_dbs(self):
        for sourcedb_name, sourcedb in self.source_couch.all_dbs_by_slug.items():
            if sourcedb_name not in self.exclude_dbs:
                print("In {} db".format(sourcedb_name or "the main"))
                yield sourcedb_name, sourcedb

    def _get_couch_database_configs_from_string(self, db_string):
        sourcedb_parse_result = urlparse(db_string)
        return CouchConfig({
            'default': {
                'COUCH_HTTPS': sourcedb_parse_result.scheme == 'https',
                'COUCH_SERVER_ROOT': sourcedb_parse_result.hostname,
                'COUCH_USERNAME': sourcedb_parse_result.username,
                'COUCH_PASSWORD': sourcedb_parse_result.password,
                'COUCH_DATABASE_NAME': sourcedb_parse_result.path.lstrip('/')
            }
        })

    def handle(self, sourcedb, domain, targetdb, **options):
        self.exclude_dbs = (
            # these have data we don't want to copy
            'receiverwrapper', 'auditcare', 'fluff-bihar',
            'fluff-mc', 'fluff-cvsu', 'mvp-indicators', 'm4change',
            # todo: missing domain/docs, but probably want to add back
            'meta',
        )
        self.source_couch = source_couch = self._get_couch_database_configs_from_string(sourcedb)
        simulate = options['simulate']
        exclude_attachments = options['exclude_attachments']
        self.run_multi_process = options['run_multi_process']

        since = json_format_date(iso_string_to_date(options['since'])) if options['since'] else None

        if options['list_types']:
            for sourcedb_name, sourcedb in self.iter_source_dbs():
                self.list_types(sourcedb, domain, since)
            sys.exit(0)

        if simulate:
            print("\nSimulated run, no data will be copied.\n")

        if options['postgres_db'] and options['postgres_password']:
            settings.DATABASES[options['postgres_db']]['PASSWORD'] = options['postgres_password']

        self.target_couch = self._get_couch_database_configs_from_string(targetdb)

        try:
            domain_doc = Domain.get_by_name(domain)
        except ResourceNotFound:
            domain_doc = None

        if domain_doc is None:
            self.copy_domain(source_couch, domain)

        if options['doc_types']:
            doc_types = options['doc_types'].split(',')
            for doc_type in doc_types:
                sourcedb = source_couch.get_db_for_doc_type(doc_type)
                startkey = [x for x in [domain, doc_type, since] if x is not None]
                endkey = [x for x in [domain, doc_type, {}] if x is not None]
                self.copy_docs(sourcedb, domain, simulate, startkey, endkey, doc_type=doc_type, since=since,
                               postgres_db=options['postgres_db'], exclude_attachments=exclude_attachments)
        elif options['id_file']:
            path = options['id_file']
            if not os.path.isfile(path):
                print("Path '%s' does not exist or is not a file" % path)
                sys.exit(1)

            with open(path) as input:
                doc_ids = [line.rstrip('\n') for line in input]

            if not doc_ids:
                print("Path '%s' does not contain any document ID's" % path)
                sys.exit(1)

            for sourcedb_name, sourcedb in self.iter_source_dbs():
                self.copy_docs(sourcedb, domain, simulate, doc_ids=doc_ids, postgres_db=options['postgres_db'],
                               exclude_attachments=exclude_attachments)
        else:
            startkey = [domain]
            endkey = [domain, {}]
            exclude_types = DEFAULT_EXCLUDE_TYPES + options['doc_types_exclude'].split(',')
            for sourcedb_name, sourcedb in self.iter_source_dbs():
                self.copy_docs(sourcedb, domain, simulate, startkey, endkey, exclude_types=exclude_types,
                               postgres_db=options['postgres_db'], exclude_attachments=exclude_attachments)

    def list_types(self, sourcedb, domain, since):
        doc_types = sourcedb.view("by_domain_doc_type_date/view", startkey=[domain],
                                  endkey=[domain, {}], reduce=True, group=True, group_level=2)

        doc_count = dict([(row['key'][1], row['value']) for row in doc_types])
        if since:
            for doc_type in sorted(six.iterkeys(doc_count)):
                num_since = sourcedb.view("by_domain_doc_type_date/view", startkey=[domain, doc_type, since],
                                          endkey=[domain, doc_type, {}], reduce=True).all()
                num = num_since[0]['value'] if num_since else 0
                print("{0:<30}- {1:<6} total {2}".format(doc_type, num, doc_count[doc_type]))
        else:
            for doc_type in sorted(six.iterkeys(doc_count)):
                print("{0:<30}- {1}".format(doc_type, doc_count[doc_type]))

    def copy_docs(self, sourcedb, domain, simulate, startkey=None, endkey=None, doc_ids=None,
                  doc_type=None, since=None, exclude_types=None, postgres_db=None, exclude_attachments=False):

        if not doc_ids:
            doc_ids = [result["id"] for result in sourcedb.view("by_domain_doc_type_date/view", startkey=startkey,
                                                                endkey=endkey, reduce=False)]
        total = len(doc_ids)
        count = 0
        msg = "Found %s matching documents in domain: %s" % (total, domain)
        msg += " of type: %s" % (doc_type) if doc_type else ""
        msg += " since: %s" % (since) if since else ""
        print(msg)

        err_log = self._get_err_log()

        if self.run_multi_process:
            queue = Queue(150)
            for i in range(NUM_PROCESSES):
                Worker(queue, sourcedb, self.target_couch, exclude_types, total, simulate, err_log, exclude_attachments).start()

            for doc in iter_docs(sourcedb, doc_ids, chunksize=100):
                count += 1
                queue.put((doc, count))

            # shutdown workers
            for i in range(NUM_PROCESSES):
                queue.put(None)
        else:
            for doc in iter_docs(sourcedb, doc_ids, chunksize=100):
                target = self.target_couch.get_db_for_doc_type(doc['doc_type'])
                count += 1
                copy_doc(doc, count, sourcedb, target, exclude_types, total, simulate, exclude_attachments)

        err_log.close()
        if os.stat(err_log.name)[6] == 0:
            os.remove(err_log.name)
        else:
            print('Failed document IDs written to %s' % err_log.name)

        if postgres_db:
            copy_postgres_data_for_docs(postgres_db, doc_ids=doc_ids, simulate=simulate)

    def copy_domain(self, source_couch, domain):
        print("Copying domain doc")
        sourcedb = source_couch.get_db_for_class(Domain)
        result = sourcedb.view(
            "domain/domains",
            key=domain,
            reduce=False,
            include_docs=True
        ).first()

        if result and 'doc' in result:
            domain_doc = Domain.wrap(result['doc'])
            dt = DocumentTransform(domain_doc._obj, sourcedb)
            save(dt, self.target_couch.get_db_for_doc_type(domain_doc['doc_type']))
        else:
            print("Domain doc not found for domain %s." % domain)

    def _get_err_log(self):
        name = 'copy_domain.err.%s'
        for i in range(1000):  # arbitrarily large number
            candidate = name % i
            if not os.path.isfile(candidate):
                return open(candidate, 'a', buffering=1)


class Worker(Process):

    def __init__(self, queue, sourcedb, target_couch, exclude_types, total, simulate, err_log, exclude_attachments):
        super(Worker, self).__init__()
        self.queue = queue
        self.sourcedb = sourcedb
        self.target_couch = target_couch
        self.exclude_types = exclude_types
        self.exclude_attachments = exclude_attachments
        self.total = total
        self.simulate = simulate
        self.err_log = err_log

    def run(self):
        for doc, count in iter(self.queue.get, None):
            try:
                target = self.target_couch.get_db_for_doc_type(doc['doc_type'])
                copy_doc(doc, count, self.sourcedb, target, self.exclude_types, self.total, self.simulate,
                         self.exclude_attachments)
            except Exception as e:
                self.err_log.write('%s\n' % doc["_id"])
                print("     Document %s failed! Error is: %s %s" % (doc["_id"], e.__class__.__name__, e))


def copy_doc(doc, count, sourcedb, target_couch, exclude_types, total, simulate, exclude_attachments):
    if exclude_types and doc["doc_type"] in exclude_types:
        print("     SKIPPED (excluded type: %s). Synced %s/%s docs (%s: %s)" % \
              (doc["doc_type"], count, total, doc["doc_type"], doc["_id"]))
    else:
        if not simulate:
            for i in reversed(list(range(5))):
                try:
                    dt = DocumentTransform(doc, sourcedb, exclude_attachments)
                    break
                except RequestError:
                    if i == 0:
                        raise
            for i in reversed(list(range(5))):
                try:
                    save(dt, target_couch)
                    break
                except (ResourceConflict, ParserError, TypeError):
                    if i == 0:
                        raise
    print("     Synced %s/%s docs (%s: %s)" % (count, total, doc["doc_type"], doc["_id"]))
