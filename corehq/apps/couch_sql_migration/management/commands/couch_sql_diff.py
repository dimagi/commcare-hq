import os
import sys

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from corehq.apps.domain.models import Domain
from corehq.form_processor.utils import should_use_sql_backend

from ...casedifftool import do_case_diffs, get_migrator
from ...couchsqlmigration import setup_logging


class Command(BaseCommand):
    help = "Diff data in couch and SQL with parallel worker processes"

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('--no-input', action='store_true', default=False)
        parser.add_argument('--debug', action='store_true', default=False)
        parser.add_argument('--state-dir',
            default=os.environ.get("CCHQ_MIGRATION_STATE_DIR"),
            required="CCHQ_MIGRATION_STATE_DIR" not in os.environ,
            help="""
                Directory for couch2sql logs and migration state. This must not
                reside on an NFS volume for migration state consistency.
                Can be set in environment: CCHQ_MIGRATION_STATE_DIR
            """)
        parser.add_argument('--live',
            dest="live", action='store_true', default=False,
            help='''
                Do not diff cases modified after the most recently
                migrated form.
            ''')
        parser.add_argument('--cases',
            help='''
                Diff specific cases. The value of this option may be
                'pending' to clear out in-process diffs OR 'with-diffs'
                to re-diff cases that previously had diffs OR a
                space-delimited list of case ids OR a path to a file
                containing a case id on each line. The path must begin
                with / or ./
            ''')
        parser.add_argument('-x', '--stop',
            dest="stop", action='store_true', default=False,
            help='''
                Stop and drop into debugger on first diff. A
                non-parallel iteration algorithm is used when this
                option is set.
            ''')
        parser.add_argument('-b', '--batch-size',
            dest="batch_size", default=100, type=int,
            help='''Diff cases in batches of this size.''')

    def handle(self, domain, **options):
        if should_use_sql_backend(domain):
            raise CommandError(f'It looks like {domain} has already been migrated.')

        for opt in ["no_input", "state_dir", "live", "cases", "stop", "batch_size"]:
            setattr(self, opt, options[opt])

        if self.no_input and not settings.UNIT_TESTING:
            raise CommandError('--no-input only allowed for unit testing')

        assert Domain.get_by_name(domain), f'Unknown domain "{domain}"'
        setup_logging(self.state_dir, "case_diff", options['debug'])
        migrator = get_migrator(domain, self.state_dir, self.live)
        msg = do_case_diffs(migrator, self.cases, self.stop, self.batch_size)
        if msg:
            sys.exit(msg)
