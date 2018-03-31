from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import datetime
from dimagi.utils.couch.database import iter_docs
from django.core.management.base import CommandError, BaseCommand
from pillowtop.feed.interface import Change
from corehq.apps.hqcase.management.commands.ptop_reindexer_v2 import FACTORIES_BY_SLUG
from corehq.util.doc_processor.couch import CouchDocumentProvider


class Command(BaseCommand):
    help = "Run a pillow on a set list of doc ids"

    def add_arguments(self, parser):
        parser.add_argument(
            '--pillow',
            action='store',
            dest='pillow',
            help="Pillow to run over doc ids",
        )
        parser.add_argument(
            '--docs',
            action='store',
            dest='docs_filename',
            help="A file containing doc ids, one per line",
        )
        parser.add_argument(
            '--skip-check',
            action='store_true',
            dest='skip_check',
            help="Skip syntax check of docs file",
            default=False,
        )

    def handle(self, **options):
        pillow = options.get('pillow', 'MISSING')
        if pillow not in FACTORIES_BY_SLUG:
            raise CommandError('--pillow must be specified and must be one of:\n{}'
                               .format(', '.join(FACTORIES_BY_SLUG)))
        reindexer = FACTORIES_BY_SLUG[pillow]().build()
        if not isinstance(reindexer.doc_provider, CouchDocumentProvider):
            raise CommandError("This command only works with couch pillows,"
                               "although it shouldn't be too hard to adapt.")
        if options['docs_filename']:
            docs_filename = options['docs_filename']
        else:
            raise CommandError('--docs argument is required')
        skip_check = options['skip_check']
        if not skip_check:
            if not self.check_file(docs_filename):
                return

        def doc_ids():
            with open(docs_filename) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        yield line

        self.handle_all(reindexer, doc_ids())

    def log(self, string):
        timestamp = datetime.datetime.utcnow().replace(microsecond=0)
        print("[{}] {}".format(timestamp, string))

    def check_file(self, docs_filename):
        ok = True
        with open(docs_filename) as f:
            for line in f:
                line = line.strip()
                if line and not self.check_id(line):
                    ok = False
                    self.log('Line in file [{}] is not a valid ID'
                             .format(line))
        return ok

    def check_id(self, id_string):
        # we can make this check better and regex it or something
        # if this ever comes up ever
        return ' ' not in id_string

    def handle_all(self, reindexer, doc_ids):
        def _change_from_couch_doc(couch_doc):
            return Change(
                id=couch_doc['_id'],
                sequence_id=None,
                document=couch_doc,
                deleted=False,
            )

        for doc in iter_docs(reindexer.doc_provider.couchdb, doc_ids):
            reindexer.pillow.process_change(_change_from_couch_doc(doc))
            self.log('PROCESSED [{}]'.format(doc['_id']))
