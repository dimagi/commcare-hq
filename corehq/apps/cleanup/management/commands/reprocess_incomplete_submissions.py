from __future__ import print_function

from __future__ import absolute_import
from __future__ import unicode_literals
import logging

from django.core.management.base import BaseCommand, CommandError
from django.core.paginator import Paginator
from django.db.models import Count

from corehq.form_processor.reprocess import reprocess_unfinished_stub
from corehq.util.log import with_progress_bar
from corehq.util.markup import SimpleTableWriter
from corehq.util.markup import TableRowFormatter
from couchforms.models import UnfinishedSubmissionStub
from six.moves import input

MODES = [
    'stats',
    'single',
    'batch',
    'all'
]

MODES_HELP = """
stats: list form count by domains
single: process one at a time with confirmation to proceed after each
batch: process in batches
all: process all without stopping for user input
"""

logger = logging.getLogger('reprocess')


def confirm():
    confirm = input(
        """
        Continue processing next batch? [y/N]
        """
    )
    return confirm == "y"


class Command(BaseCommand):
    help = ('Reprocesses unfinished form submissions')

    def add_arguments(self, parser):
        parser.add_argument('mode', help=MODES_HELP, choices=MODES)
        parser.add_argument('--domain', help='Restrict queries to submissions in this domain')
        parser.add_argument('--batch_size', default=10, type=int)
        parser.add_argument(
            '--verbose',
            action='store_true',
            dest='verbose',
            default=False,
        )
        parser.add_argument(
            '--dryrun',
            action='store_true',
            dest='dryrun',
            default=False,
            help="Don't do the actual reprocessing, just print the ids that would be affected",
        )

    def handle(self, domain, **options):
        dryrun = options["dryrun"]
        verbose = options["verbose"] or dryrun

        mode = options['mode']
        if mode == 'stats':
            self.print_stats()
            return

        batch_size = {
            'single': 1,
            'batch': options['batch_size'],
            'all': None
        }[mode]

        if verbose and batch_size:
            root_logger = logging.getLogger('')
            root_logger.setLevel(logging.DEBUG)

        if not batch_size:
            if dryrun:
                raise CommandError('Dry run only for single / batch modes')
            total = UnfinishedSubmissionStub.objects.count()
            stub_iterator = with_progress_bar(UnfinishedSubmissionStub.objects.all(), total, oneline=False)
            for stub in stub_iterator:
                reprocess_unfinished_stub(stub)
        else:
            paginator = Paginator(UnfinishedSubmissionStub.objects.all(), batch_size)
            for page_number in paginator.page_range:
                page = paginator.page(page_number)
                for stub in page.object_list:
                    result = reprocess_unfinished_stub(stub, save=not dryrun)
                    if result:
                        cases = ', '.join([c.case_id for c in result.cases])
                        ledgers = ', '.join([l.ledger_reference for l in result.ledgers])
                        logger.info("Form re-processed successfully: {}:{}".format(
                            result.form.domain, result.form.form_id, cases, ledgers
                        ))
                if not page.has_next():
                    print("All forms processed")
                elif not confirm():
                    break

    def print_stats(self):
        stats = UnfinishedSubmissionStub.objects.all().values('domain')\
            .annotate(count=Count('domain')).order_by('count')
        writer = SimpleTableWriter(self.stdout, TableRowFormatter([50, 10]))
        writer.write_table(['Domain', '# Forms'], [
            (stat['domain'], stat['count']) for stat in stats
        ])
