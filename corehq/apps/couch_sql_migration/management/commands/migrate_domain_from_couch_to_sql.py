# encoding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
from itertools import groupby

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from six.moves import input, zip_longest
from sqlalchemy.exc import OperationalError

from corehq.apps.couch_sql_migration.couchsqlmigration import (
    CASE_DOC_TYPES,
    delete_diff_db,
    do_couch_to_sql_migration,
    get_diff_db,
    setup_logging,
)
from corehq.apps.couch_sql_migration.progress import (
    couch_sql_migration_in_progress,
    get_couch_sql_migration_status,
    set_couch_sql_migration_complete,
    set_couch_sql_migration_not_started,
    set_couch_sql_migration_started,
)
from corehq.apps.domain.dbaccessors import get_doc_ids_in_domain_by_type
from corehq.apps.hqcase.dbaccessors import get_case_ids_in_domain
from corehq.apps.tzmigration.planning import Counts
from corehq.form_processor.backends.sql.dbaccessors import (
    CaseAccessorSQL,
    FormAccessorSQL,
)
from corehq.form_processor.utils import should_use_sql_backend
from corehq.util.markup import shell_green, shell_red
from couchforms.dbaccessors import get_form_ids_by_type
from couchforms.models import XFormInstance, doc_types

log = logging.getLogger('main_couch_sql_datamigration')

# Script action constants
MIGRATE = "MIGRATE"
COMMIT = "COMMIT"
RESET = "reset"  # was --blow-away
STATS = "stats"
DIFF = "diff"


class Command(BaseCommand):
    help = """
    Step 1: Run 'MIGRATE'
    Step 2a: If diffs, use 'diff' to view diffs
    Step 2b: Use 'stats --verbose' to view more stats output
    Step 3: If no diffs or diffs are acceptable run 'COMMIT'
    Step 4: Run 'reset' to abort the current migration
    """

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('action', choices=[
            MIGRATE,
            COMMIT,
            RESET,
            STATS,
            DIFF,
        ])
        parser.add_argument('--no-input', action='store_true', default=False)
        parser.add_argument('--debug', action='store_true', default=False)
        parser.add_argument('--verbose', action='store_true', default=False,
            help="Show verbose stats output.")
        parser.add_argument('--log-dir', help="""
            Directory for couch2sql logs, which are not written if this is not
            provided. Standard HQ logs will be used regardless of this setting.
        """)
        parser.add_argument('--dry-run', action='store_true', default=False,
            help='''
                Do migration in a way that will not be seen by
                `any_migrations_in_progress(...)` so it does not block
                operations like syncs, form submissions, sms activity,
                etc. Dry-run migrations cannot be committed.
            ''')
        parser.add_argument(
            '--run-timestamp',
            type=int,
            default=None,
            help='use this option to continue a previous run that was started at this timestamp'
        )

    def handle(self, domain, action, **options):
        if should_use_sql_backend(domain):
            raise CommandError('It looks like {} has already been migrated.'.format(domain))

        for opt in ["no_input", "debug", "verbose", "dry_run", "run_timestamp"]:
            setattr(self, opt, options[opt])

        if self.no_input and not settings.UNIT_TESTING:
            raise CommandError('--no-input only allowed for unit testing')
        if action != MIGRATE and self.dry_run:
            raise CommandError("--dry-run only allowed for `MIGRATE`")
        if action != STATS and self.verbose:
            raise CommandError("--verbose only allowed for `stats`")

        setup_logging(options['log_dir'])
        getattr(self, "do_" + action)(domain)

    def do_MIGRATE(self, domain):
        if self.run_timestamp:
            if not couch_sql_migration_in_progress(domain):
                raise CommandError("Migration must be in progress if --run-timestamp is provided")
        else:
            set_couch_sql_migration_started(domain, self.dry_run)

        do_couch_to_sql_migration(
            domain,
            with_progress=not self.no_input,
            debug=self.debug,
            run_timestamp=self.run_timestamp)

        has_diffs = self.print_stats(domain, short=True, diffs_only=True)
        if has_diffs:
            print("\nRun `diff` or `stats --verbose` for more details.\n")

    def do_reset(self, domain):
        if not self.no_input:
            _confirm(
                "This will delete all SQL forms and cases for the domain {}. "
                "Are you sure you want to continue?".format(domain)
            )
        set_couch_sql_migration_not_started(domain)
        blow_away_migration(domain)

    def do_stats(self, domain):
        self.print_stats(domain, short=not self.verbose)

    def do_COMMIT(self, domain):
        if not couch_sql_migration_in_progress(domain, include_dry_runs=False):
            raise CommandError("cannot commit a migration that is not in state in_progress")
        if not self.no_input:
            _confirm(
                "This will convert the domain to use the SQL backend and"
                "allow new form submissions to be processed. "
                "Are you sure you want to do this for domain '{}'?".format(domain)
            )
        set_couch_sql_migration_complete(domain)

    def do_diff(self, domain):
        db = get_diff_db(domain)
        diffs = sorted(db.get_diffs(), key=lambda d: d.kind)
        for doc_type, diffs in groupby(diffs, key=lambda d: d.kind):
            print('-' * 50, "Diffs for {}".format(doc_type), '-' * 50)
            for diff in diffs:
                print('[{}({})] {}'.format(doc_type, diff.doc_id, diff.json_diff))

    def print_stats(self, domain, short=True, diffs_only=False):
        status = get_couch_sql_migration_status(domain)
        print("Couch to SQL migration status for {}: {}".format(domain, status))
        db = get_diff_db(domain)
        try:
            diff_stats = db.get_diff_stats()
        except OperationalError:
            diff_stats = {}

        has_diffs = False
        for doc_type in doc_types():
            form_ids_in_couch = set(get_form_ids_by_type(domain, doc_type))
            form_ids_in_sql = set(FormAccessorSQL.get_form_ids_in_domain_by_type(domain, doc_type))
            diff_count, num_docs_with_diffs = diff_stats.pop(doc_type, (0, 0))
            has_diffs |= self._print_status(
                doc_type, form_ids_in_couch, form_ids_in_sql, diff_count, num_docs_with_diffs, short, diffs_only
            )

        form_ids_in_couch = set(get_doc_ids_in_domain_by_type(
            domain, "XFormInstance-Deleted", XFormInstance.get_db())
        )
        form_ids_in_sql = set(FormAccessorSQL.get_deleted_form_ids_in_domain(domain))
        diff_count, num_docs_with_diffs = diff_stats.pop("XFormInstance-Deleted", (0, 0))
        has_diffs |= self._print_status(
            "XFormInstance-Deleted", form_ids_in_couch, form_ids_in_sql,
            diff_count, num_docs_with_diffs, short, diffs_only
        )

        ZERO = Counts(0, 0)
        if db.has_doc_counts():
            doc_counts = db.get_doc_counts()
        else:
            doc_counts = None
        for doc_type in CASE_DOC_TYPES:
            if doc_counts is not None:
                counts = doc_counts.get(doc_type, ZERO)
                case_ids_in_couch = db.get_missing_doc_ids(doc_type) if counts.missing else set()
                case_ids_in_sql = counts
            elif doc_type == "CommCareCase":
                case_ids_in_couch = set(get_case_ids_in_domain(domain))
                case_ids_in_sql = set(CaseAccessorSQL.get_case_ids_in_domain(domain))
            elif doc_type == "CommCareCase-Deleted":
                case_ids_in_couch = set(get_doc_ids_in_domain_by_type(
                    domain, "CommCareCase-Deleted", XFormInstance.get_db())
                )
                case_ids_in_sql = set(CaseAccessorSQL.get_deleted_case_ids_in_domain(domain))
            else:
                raise NotImplementedError(doc_type)
            diff_count, num_docs_with_diffs = diff_stats.pop(doc_type, (0, 0))
            has_diffs |= self._print_status(
                doc_type,
                case_ids_in_couch,
                case_ids_in_sql,
                diff_count,
                num_docs_with_diffs,
                short,
                diffs_only,
            )

        if diff_stats:
            for key, counts in diff_stats.items():
                diff_count, num_docs_with_diffs = counts
                has_diffs |= self._print_status(
                    key, set(), set(), diff_count, num_docs_with_diffs, short, diffs_only
                )

        if diffs_only and not has_diffs:
            print(shell_green("No differences found between old and new docs!"))
        return has_diffs

    def _print_status(self, name, ids_in_couch, ids_in_sql, diff_count, num_docs_with_diffs, short, diffs_only):
        if isinstance(ids_in_sql, Counts):
            counts, ids_in_sql = ids_in_sql, set()
            assert len(ids_in_couch) == counts.missing, (len(ids_in_couch), counts.missing)
            n_couch = counts.total
            n_sql = counts.total - counts.missing
        else:
            n_couch = len(ids_in_couch)
            n_sql = len(ids_in_sql)
        has_diff = ids_in_couch != ids_in_sql or diff_count

        if diffs_only and not has_diff:
            return False

        def _highlight(text):
            return shell_red(text) if has_diff else text

        row = "{:^38} {} {:^38}"
        sep = "|" if ids_in_couch == ids_in_sql else "≠"
        doc_count_row = row.format(n_couch, sep, n_sql)

        print('\n{:_^79}'.format(" %s " % name))
        print(row.format('Couch', '|', 'SQL'))
        print(_highlight(doc_count_row))
        if diff_count:
            print(_highlight("{:^83}".format('{} diffs ({} docs)'.format(diff_count, num_docs_with_diffs))))

        if not short:
            if ids_in_couch ^ ids_in_sql:
                couch_only = list(ids_in_couch - ids_in_sql)
                sql_only = list(ids_in_sql - ids_in_couch)
                for couch, sql in zip_longest(couch_only, sql_only):
                    print(row.format(couch or '', '|', sql or ''))

        return True


def _confirm(message):
    response = input('{} [y/N]'.format(message)).lower()
    if response != 'y':
        raise CommandError('abort')


def blow_away_migration(domain):
    assert not should_use_sql_backend(domain)
    delete_diff_db(domain)

    for doc_type in doc_types():
        sql_form_ids = FormAccessorSQL.get_form_ids_in_domain_by_type(domain, doc_type)
        FormAccessorSQL.hard_delete_forms(domain, sql_form_ids, delete_attachments=False)

    sql_form_ids = FormAccessorSQL.get_deleted_form_ids_in_domain(domain)
    FormAccessorSQL.hard_delete_forms(domain, sql_form_ids, delete_attachments=False)

    sql_case_ids = CaseAccessorSQL.get_case_ids_in_domain(domain)
    CaseAccessorSQL.hard_delete_cases(domain, sql_case_ids)

    sql_case_ids = CaseAccessorSQL.get_deleted_case_ids_in_domain(domain)
    CaseAccessorSQL.hard_delete_cases(domain, sql_case_ids)
    log.info("blew away migration for domain {}\n".format(domain))
