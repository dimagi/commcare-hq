from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from itertools import groupby

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from sqlalchemy.exc import OperationalError

from corehq.apps.couch_sql_migration.couchsqlmigration import (
    do_couch_to_sql_migration,
    delete_diff_db,
    get_diff_db,
    revert_form_attachment_meta_domain,
)
from corehq.apps.couch_sql_migration.progress import (
    set_couch_sql_migration_started,
    couch_sql_migration_in_progress,
    set_couch_sql_migration_not_started,
    set_couch_sql_migration_complete,
)
from corehq.apps.domain.dbaccessors import get_doc_ids_in_domain_by_type
from corehq.apps.hqcase.dbaccessors import get_case_ids_in_domain
from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL, CaseAccessorSQL
from corehq.form_processor.utils import should_use_sql_backend
from corehq.util.markup import shell_green, shell_red
from couchforms.dbaccessors import get_form_ids_by_type
from couchforms.models import doc_types, XFormInstance
from six.moves import input, zip_longest

import logging
_logger = logging.getLogger('main_couch_sql_datamigration')


class Command(BaseCommand):
    help = """
    Step 1: Run with '--MIGRATE'
    Step 2a: If no diffs or diffs acceptable run with '--COMMIT'
    Step 2b: If diffs, use '--show-diffs' to view diffs
    Step 3: Run with '--blow-away' to abort
    """

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('--dest')
        parser.add_argument('--MIGRATE', action='store_true', default=False)
        parser.add_argument('--COMMIT', action='store_true', default=False)
        parser.add_argument('--blow-away', action='store_true', default=False)
        parser.add_argument('--stats-short', action='store_true', default=False)
        parser.add_argument('--stats-long', action='store_true', default=False)
        parser.add_argument('--show-diffs', action='store_true', default=False)
        parser.add_argument('--no-input', action='store_true', default=False)
        parser.add_argument('--debug', action='store_true', default=False)
        parser.add_argument('--dry-run', action='store_true', default=False)
        parser.add_argument(
            '--run-timestamp',
            type=int,
            default=None,
            help='use this option to continue a previous run that was started at this timestamp'
        )

    @staticmethod
    def require_only_option(sole_option, options):
        this_command_opts = {
            'MIGRATE',
            'COMMIT',
            'blow_away',
            'stats',
            'show_diffs',
            'no_input',
            'debug',
            'dry_run',
        }
        for key, value in options.items():
            if value and key in this_command_opts and key != sole_option:
                raise CommandError("%s must be the sole option used" % key)

    def handle(self, domain, **options):
        if should_use_sql_backend(domain):
            raise CommandError('It looks like {} has already been migrated.'.format(domain))

        self.no_input = options.pop('no_input', False)
        self.debug = options.pop('debug', False)
        self.dry_run = options.pop('dry_run', False)

        if self.no_input and not settings.UNIT_TESTING:
            raise CommandError('no-input only allowed for unit testing')

        dst_domain = options.pop('dest', None) or domain

        if options['MIGRATE']:
            self.require_only_option('MIGRATE', options)

            if options.get('run_timestamp'):
                if not couch_sql_migration_in_progress(domain):
                    raise CommandError("Migration must be in progress if run_timestamp is passed in")
            else:
                set_couch_sql_migration_started(domain, self.dry_run)
                set_couch_sql_migration_started(dst_domain, self.dry_run)  # Required at corehq/form_processor/interfaces/processor.py:253
                                                                           # TODO: Although this is probably a terrible idea

            do_couch_to_sql_migration(
                domain,
                dst_domain=dst_domain,
                with_progress=not self.no_input,
                debug=self.debug,
                run_timestamp=options.get('run_timestamp'))

            has_diffs = self.print_stats(domain, dst_domain, short=True, diffs_only=True)
            if has_diffs:
                print("\nUse '--stats-short', '--stats-long', '--show-diffs' to see more info.\n")

        if options['blow_away']:
            self.require_only_option('blow_away', options)
            if not self.no_input:
                _confirm(
                    "This will delete all SQL forms and cases for the domain {}. "
                    "Are you sure you want to continue?".format(dst_domain)
                )
            set_couch_sql_migration_not_started(domain)
            set_couch_sql_migration_not_started(dst_domain)
            _blow_away_migration(domain, dst_domain)

        if options['stats_short'] or options['stats_long']:
            self.print_stats(domain, dst_domain, short=options['stats_short'])
        if options['show_diffs']:
            self.show_diffs(domain)

        if options['COMMIT']:
            # This is not applicable when domain != dst_domain. Once
            # domain has been migrated, it should continue to prevent
            # form submissions.
            self.require_only_option('COMMIT', options)
            if not couch_sql_migration_in_progress(domain, include_dry_runs=False):
                raise CommandError("cannot commit a migration that is not in state in_progress")
            if not self.no_input:
                _confirm(
                    "This will convert the domain to use the SQL backend and"
                    "allow new form submissions to be processed. "
                    "Are you sure you want to do this for domain '{}'?".format(domain)
                )
            set_couch_sql_migration_complete(domain)

    def show_diffs(self, domain):
        db = get_diff_db(domain)
        diffs = sorted(db.get_diffs(), key=lambda d: d.kind)
        for doc_type, diffs in groupby(diffs, key=lambda d: d.kind):
            print('-' * 50, "Diffs for {}".format(doc_type), '-' * 50)
            for diff in diffs:
                print('[{}({})] {}'.format(doc_type, diff.doc_id, diff.json_diff))

    def print_stats(self, src_domain, dst_domain, short=True, diffs_only=False):
        db = get_diff_db(src_domain)
        try:
            diff_stats = db.get_diff_stats()
        except OperationalError:
            diff_stats = {}

        has_diffs = False
        for doc_type in doc_types():
            form_ids_in_couch = set(get_form_ids_by_type(src_domain, doc_type))
            form_ids_in_sql = set(FormAccessorSQL.get_form_ids_in_domain_by_type(dst_domain, doc_type))
            diff_count, num_docs_with_diffs = diff_stats.pop(doc_type, (0, 0))
            has_diffs |= self._print_status(
                doc_type, form_ids_in_couch, form_ids_in_sql, diff_count, num_docs_with_diffs, short, diffs_only
            )

        form_ids_in_couch = set(get_doc_ids_in_domain_by_type(
            src_domain, "XFormInstance-Deleted", XFormInstance.get_db())
        )
        form_ids_in_sql = set(FormAccessorSQL.get_deleted_form_ids_in_domain(dst_domain))
        diff_count, num_docs_with_diffs = diff_stats.pop("XFormInstance-Deleted", (0, 0))
        has_diffs |= self._print_status(
            "XFormInstance-Deleted", form_ids_in_couch, form_ids_in_sql,
            diff_count, num_docs_with_diffs, short, diffs_only
        )

        case_ids_in_couch = set(get_case_ids_in_domain(src_domain))
        case_ids_in_sql = set(CaseAccessorSQL.get_case_ids_in_domain(dst_domain))
        diff_count, num_docs_with_diffs = diff_stats.pop("CommCareCase", (0, 0))
        has_diffs |= self._print_status(
            'CommCareCase', case_ids_in_couch, case_ids_in_sql, diff_count, num_docs_with_diffs, short, diffs_only
        )

        case_ids_in_couch = set(get_doc_ids_in_domain_by_type(
            src_domain, "CommCareCase-Deleted", XFormInstance.get_db())
        )
        case_ids_in_sql = set(CaseAccessorSQL.get_deleted_case_ids_in_domain(dst_domain))
        diff_count, num_docs_with_diffs = diff_stats.pop("CommCareCase-Deleted", (0, 0))
        has_diffs |= self._print_status(
            'CommCareCase-Deleted', case_ids_in_couch, case_ids_in_sql,
            diff_count, num_docs_with_diffs, short, diffs_only
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
        n_couch = len(ids_in_couch)
        n_sql = len(ids_in_sql)
        has_diff = n_couch != n_sql or diff_count

        if diffs_only and not has_diff:
            return False

        def _highlight(text):
            return shell_red(text) if has_diff else text

        row = "{:^40} | {:^40}"
        doc_count_row = row.format(n_couch, n_sql)
        header = ((82 - len(name)) // 2) * '_'

        print('\n{} {} {}'.format(header, name, header))
        print(row.format('Couch', 'SQL'))
        print(_highlight(doc_count_row))
        if diff_count:
            print(_highlight("{:^83}".format('{} diffs ({} docs)'.format(diff_count, num_docs_with_diffs))))

        if not short:
            if ids_in_couch ^ ids_in_sql:
                couch_only = list(ids_in_couch - ids_in_sql)
                sql_only = list(ids_in_sql - ids_in_couch)
                for couch, sql in zip_longest(couch_only, sql_only):
                    print(row.format(couch or '', sql or ''))

        return True


def _confirm(message):
    if input(
            '{} [y/n]'.format(message)
    ).lower() == 'y':
        return
    else:
        raise CommandError('abort')


def _blow_away_migration(src_domain, dst_domain=None):
    if dst_domain is None:
        dst_domain = src_domain
    if src_domain == dst_domain:
        # If src_domain and dst_domain are different their backends don't change
        assert not should_use_sql_backend(src_domain)
    delete_diff_db(src_domain)

    if src_domain != dst_domain:
        revert_form_attachment_meta_domain(src_domain)

    for doc_type in doc_types():
        sql_form_ids = FormAccessorSQL.get_form_ids_in_domain_by_type(dst_domain, doc_type)
        FormAccessorSQL.hard_delete_forms(dst_domain, sql_form_ids, delete_attachments=False)

    sql_form_ids = FormAccessorSQL.get_deleted_form_ids_in_domain(dst_domain)
    FormAccessorSQL.hard_delete_forms(dst_domain, sql_form_ids, delete_attachments=False)

    sql_case_ids = CaseAccessorSQL.get_case_ids_in_domain(dst_domain)
    CaseAccessorSQL.hard_delete_cases(dst_domain, sql_case_ids)

    sql_case_ids = CaseAccessorSQL.get_deleted_case_ids_in_domain(dst_domain)
    CaseAccessorSQL.hard_delete_cases(dst_domain, sql_case_ids)
    _logger.info("blew away migration for domain {}".format(src_domain))
