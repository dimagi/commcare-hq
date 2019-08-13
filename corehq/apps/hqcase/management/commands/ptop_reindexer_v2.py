from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management import BaseCommand, CommandError

from corehq.pillows.app_submission_tracker import (
    CouchAppFormSubmissionTrackerReindexerFactory,
    SqlAppFormSubmissionTrackerReindexerFactory,
    UserAppFormSubmissionReindexerFactory
)
from corehq.pillows.application import AppReindexerFactory
from corehq.pillows.case import (
    CouchCaseReindexerFactory, SqlCaseReindexerFactory
)
from corehq.pillows.case_search import CaseSearchReindexerFactory, ResumableCaseSearchReindexerFactory
from corehq.pillows.domain import DomainReindexerFactory
from corehq.pillows.group import GroupReindexerFactory
from corehq.pillows.groups_to_user import GroupToUserReindexerFactory
from corehq.pillows.reportcase import ReportCaseReindexerFactory
from corehq.pillows.reportxform import ReportFormReindexerFactory
from corehq.pillows.sms import SmsReindexerFactory
from corehq.pillows.synclog import UpdateUserSyncHistoryReindexerFactory
from corehq.pillows.user import UserReindexerFactory
from corehq.pillows.xform import CouchFormReindexerFactory, SqlFormReindexerFactory
from corehq.util.test_utils import unit_testing_only
from six.moves import input

USAGE = """Reindex a pillowtop index.

To get help for a specific reindexer user:

    ./manage.py ptop_reindexer_v2 [reindexer] -h
"""


FACTORIES = [
    DomainReindexerFactory,
    UserReindexerFactory,
    GroupReindexerFactory,
    GroupToUserReindexerFactory,
    CouchCaseReindexerFactory,
    CouchFormReindexerFactory,
    SqlCaseReindexerFactory,
    SqlFormReindexerFactory,
    CaseSearchReindexerFactory,
    ResumableCaseSearchReindexerFactory,
    SmsReindexerFactory,
    ReportCaseReindexerFactory,
    ReportFormReindexerFactory,
    AppReindexerFactory,
    CouchAppFormSubmissionTrackerReindexerFactory,
    SqlAppFormSubmissionTrackerReindexerFactory,
    UpdateUserSyncHistoryReindexerFactory,
    UserAppFormSubmissionReindexerFactory,
]


FACTORIES_BY_SLUG = {
    factory.slug: factory
    for factory in FACTORIES
}


@unit_testing_only
def reindex_and_clean(slug, **options):
    reindexer = FACTORIES_BY_SLUG[slug](**options).build()
    reindexer.clean()
    reindexer.reindex()


class SubCommand(BaseCommand):
    subcommands = {}

    def run_from_argv(self, argv):
        self.subcommand = None
        if len(argv) >= 3 and argv[2] in self.subcommands:
            self.subcommand = argv[2]
            argv = argv[0:2] + argv[3:]
            super(SubCommand, self).run_from_argv(argv)
        else:
            super(SubCommand, self).run_from_argv(argv)

    def create_parser(self, prog_name, command_name):
        parser = super(SubCommand, self).create_parser(prog_name, command_name)
        if self.subcommand:
            self.add_subcommand_arguments(parser, self.subcommand)
        return parser

    def add_arguments(self, parser):
        if not self.subcommand:
            parser.add_argument(
                'subcommand',
                choices=list(self.subcommands),
            )
        self.add_global_arguments(parser)

    def add_subcommand_arguments(self, parser, subcommand):
        pass

    def add_global_arguments(self, parser):
        pass


class Command(SubCommand):
    help = USAGE
    subcommands = FACTORIES_BY_SLUG

    def add_global_arguments(self, parser):
        parser.add_argument(
            '--cleanup',
            action='store_true',
            dest='cleanup',
            default=False,
            help='Clean index (delete data) before reindexing.'
        )
        parser.add_argument(
            '--noinput',
            action='store_true',
            dest='noinput',
            default=False,
            help='Skip important confirmation warnings.'
        )

    def add_subcommand_arguments(self, parser, subcommand):
        FACTORIES_BY_SLUG[subcommand].add_arguments(parser)

    def handle(self, **options):
        cleanup = options.pop('cleanup')
        noinput = options.pop('noinput')

        for option in ['settings', 'pythonpath', 'verbosity', 'traceback', 'no_color']:
            options.pop(option, None)

        def confirm():
            return input("Are you sure you want to delete the current index (if it exists)? y/n\n") == 'y'

        factory = FACTORIES_BY_SLUG[self.subcommand](**options)
        reindexer = factory.build()

        if cleanup and (noinput or confirm()):
            reindexer.clean()

        reindexer.reindex()
