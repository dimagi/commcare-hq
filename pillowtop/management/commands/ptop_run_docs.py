import datetime
from dimagi.utils.couch.database import iter_docs
from django.core.management.base import LabelCommand, CommandError, BaseCommand
from optparse import make_option
from pillowtop import get_pillow_by_name
from pillowtop.feed.interface import Change


class Command(BaseCommand):
    help = "Run a pillow on a set list of doc ids"
    args = "--pillow=<Pillow> --docs=<doc"

    option_list = BaseCommand.option_list + (
        make_option(
            '--pillow',
            action='store',
            dest='pillow_class',
            help="Pillow class to run over doc ids",
        ),
        make_option(
            '--docs',
            action='store',
            dest='docs_filename',
            help="A file containing doc ids, one per line",
        ),
        make_option(
            '--skip-check',
            action='store_true',
            dest='skip_check',
            help="Skip syntax check of docs file",
            default=False,
        )
    )

    def handle(self, *args, **options):
        if options['pillow_class']:
            pillow = get_pillow_by_name(options['pillow_class'])
        else:
            raise CommandError('--pillow argument is required')
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

        self.handle_all(pillow, doc_ids())

    def log(self, string):
        timestamp = datetime.datetime.utcnow().replace(microsecond=0)
        print "[{}] {}".format(timestamp, string)

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

    def handle_all(self, pillow, doc_ids):
        def _change_from_couch_doc(couch_doc):
            return Change(
                id=couch_doc['_id'],
                sequence_id=None,
                document=couch_doc,
                deleted=False,
            )

        for doc in iter_docs(pillow.couch_db, doc_ids):
            pillow.process_change(_change_from_couch_doc(doc))
            self.log('PROCESSED [{}]'.format(doc['_id']))
