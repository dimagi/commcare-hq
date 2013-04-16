import sys
from django.core.management.base import BaseCommand, CommandError
from dimagi.utils.couch.database import get_db, iter_docs
from corehq.apps.domainsync.config import DocumentTransform, save
from couchdbkit.client import Database
from optparse import make_option
from datetime import datetime

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
                    default='ReportNotification',
                    help='Comma-separated list of Document Types to NOT copy.'),
        make_option('--since',
                    action='store',
                    dest='since',
                    default='',
                    help='Only copy documents newer thank this date. Format: yyyy-MM-dd. Only '),
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
            self.list_types(sourcedb, domain)
            sys.exit(0)

        if simulate:
            print "\nSimulated run, no data will be copied.\n"

        if options['doc_types']:
            doc_types = options['doc_types'].split(',')
            for type in doc_types:
                startkey = [x for x in [domain, type, since] if x is not None]
                endkey = [x for x in [domain, type, {}] if x is not None]
                self.copy_docs(sourcedb, domain, startkey, endkey, simulate, type=type, since=since)
        else:
            startkey = [domain]
            endkey = [domain, {}]
            exclude_types = options['doc_types_exclude'].split(',')
            self.copy_docs(sourcedb, domain, startkey, endkey, simulate, exclude_types=exclude_types)

    def list_types(self, sourcedb, domain):
        doc_types = sourcedb.view("domain/docs", startkey=[domain],
                                  endkey=[domain, {}], reduce=True, group=True, group_level=2)
        for row in doc_types:
            print "{:<30}- {}".format(row['key'][1], row['value'])

    def copy_docs(self, sourcedb, domain, startkey, endkey, simulate, type=None, since=None, exclude_types=None):
        doc_ids = [result["id"] for result in sourcedb.view("domain/docs", startkey=startkey,
                             endkey=endkey, reduce=False)]

        total = len(doc_ids)
        count = 0
        targetdb = get_db()
        msg = "Found %s matching documents in domain: %s" % (total, domain)
        msg += " of type: %s" % (type) if type else ""
        msg += " since: %s" % (since) if since else ""
        print msg
        for doc in iter_docs(sourcedb, doc_ids):
            try:
                count += 1
                if exclude_types and doc["doc_type"] in exclude_types:
                    print "     SKIPPED (excluded type: %s). Synced %s/%s docs (%s: %s)" % \
                          (doc["doc_type"], count, total, doc["doc_type"], doc["_id"])
                else:
                    if not simulate:
                        dt = DocumentTransform(doc, sourcedb)
                        save(dt, targetdb)
                    print "     Synced %s/%s docs (%s: %s)" % (count, total, doc["doc_type"], doc["_id"])
            except Exception, e:
                print "     Document %s failed! Error is: %s" % (doc["_id"], e)
