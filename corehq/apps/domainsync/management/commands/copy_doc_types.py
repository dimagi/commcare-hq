from __future__ import absolute_import
from __future__ import unicode_literals
import logging

from django.core.management.base import BaseCommand
from couchdbkit.client import Database

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Copies all docs of some types from one database to another. Pretty brute force and single-threaded."

    def add_arguments(self, parser):
        parser.add_argument(
            'sourcedb',
        )
        parser.add_argument(
            'destdb',
        )
        parser.add_argument(
            'doc_type',
            dest='doc_types',
            help='Comma-separated list of Document Types to copy',
            nargs='*',
        )
        parser.add_argument(
            '--pretend',
            action='store_true',
            dest='pretend',
            default=False,
            help='Don\'t copy anything, print what would be copied.',
        )

    def handle(self, sourcedb, destdb, doc_types, **options):
        sourcedb = Database(sourcedb)
        destdb = Database(destdb)
        pretend = options['pretend']

        if pretend:
            logger.info("**** Simulated run, no data will be copied. ****")

        self.copy_docs(sourcedb, destdb, pretend=pretend, doc_types=doc_types)

    def iter_view(self, db, view_name, startkey=None, endkey=None, reduce=False, chunksize=1000):
        "iterates over the raw docs of the view in chunks of a safe size for couchdb requests"

        for chunk in self.iter_chunks(db,
                                      view_name,
                                      startkey=startkey,
                                      endkey=endkey,
                                      reduce=reduce,
                                      chunksize=chunksize):
            for row in chunk:
                yield row['doc']

    def iter_chunks(self, db, view_name, startkey=None, endkey=None, reduce=False, chunksize=1000):
        "iterates over chunks of the raw docs of the view, for bulk processing"

        # A recursive formulation is superior but Python does not optimize tail calls
        more_to_fetch = True
        nextkey = startkey

        while more_to_fetch:

            chunk = db.view(
                view_name,
                startkey=nextkey,
                endkey=endkey,
                reduce=reduce,
                include_docs=True,
                limit=chunksize + 1 # The last doc provides the startkey for the next chunk
            )

            rows = chunk.all()

            yield [row['doc'] for row in rows[:chunksize]]

            if len(rows) <= chunksize:
                more_to_fetch = False
                nextkey = None
            else:
                nextkey = rows[-1]['key']

    def copy_docs(self, sourcedb, destdb, pretend=False, doc_types=None):
        doc_types = doc_types or []
        metadata = sourcedb.view('_all_docs', limit=0)
        processed = 0

        for chunk in self.iter_chunks(sourcedb, '_all_docs'):
            processed += len(chunk)
            logger.info('%d/%d docs considered' % (processed, metadata.total_rows))

            docs_to_copy = [doc for doc in chunk if doc.get('doc_type') and doc['doc_type'] in doc_types]

            for doc in docs_to_copy:
                if '_rev' in doc:
                    del doc['_rev']

            if len(docs_to_copy) > 0:
                if not pretend:
                    destdb.bulk_save(docs_to_copy, new_edits=False)
                logger.info('%d matching docs copied', len(docs_to_copy))
