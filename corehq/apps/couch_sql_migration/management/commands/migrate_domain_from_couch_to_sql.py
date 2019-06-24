# encoding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
from itertools import groupby

import six
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from six.moves import input, zip_longest
from sqlalchemy.exc import OperationalError

from corehq.blobs import get_blob_db, CODES
from corehq.form_processor.change_publishers import publish_case_saved, publish_form_saved
from couchforms.dbaccessors import get_form_ids_by_type
from couchforms.models import XFormInstance, doc_types

from corehq import toggles
from corehq.apps.couch_sql_migration.couchsqlmigration import (
    CASE_DOC_TYPES,
    delete_diff_db,
    do_couch_to_sql_migration,
    get_diff_db,
    revert_form_attachment_meta_domain,
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
from dimagi.utils.chunked import chunked
from dimagi.utils.couch.database import iter_docs

log = logging.getLogger('main_couch_sql_datamigration')


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

        setup_logging(options['log_dir'])
        if options['MIGRATE']:
            self.require_only_option('MIGRATE', options)

            if options.get('run_timestamp'):
                if not couch_sql_migration_in_progress(domain):
                    raise CommandError("Migration must be in progress if run_timestamp is passed in")
            else:
                set_couch_sql_migration_started(domain, self.dry_run)
                if domain != dst_domain:
                    set_couch_sql_migration_started(dst_domain, self.dry_run)

            do_couch_to_sql_migration(
                domain,
                dst_domain=dst_domain,
                with_progress=not self.no_input,
                debug=self.debug,
                run_timestamp=options.get('run_timestamp'),
                dry_run=self.dry_run,
            )

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
            if domain != dst_domain:
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
            if domain == dst_domain:
                set_couch_sql_migration_complete(domain)
            else:
                _commit_src_domain(domain)
                _commit_dst_domain(dst_domain)

    def show_diffs(self, domain):
        db = get_diff_db(domain)
        diffs = sorted(db.get_diffs(), key=lambda d: d.kind)
        for doc_type, diffs in groupby(diffs, key=lambda d: d.kind):
            print('-' * 50, "Diffs for {}".format(doc_type), '-' * 50)
            for diff in diffs:
                print('[{}({})] {}'.format(doc_type, diff.doc_id, diff.json_diff))

    def print_stats(self, src_domain, dst_domain, short=True, diffs_only=False):
        status = get_couch_sql_migration_status(src_domain)
        print("Couch to SQL migration status for {}: {}".format(src_domain, status))
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
                case_ids_in_couch = set(get_case_ids_in_domain(src_domain))
                case_ids_in_sql = set(CaseAccessorSQL.get_case_ids_in_domain(dst_domain))
            elif doc_type == "CommCareCase-Deleted":
                case_ids_in_couch = set(get_doc_ids_in_domain_by_type(
                    src_domain, "CommCareCase-Deleted", XFormInstance.get_db())
                )
                case_ids_in_sql = set(CaseAccessorSQL.get_deleted_case_ids_in_domain(dst_domain))
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
        print(_highlight(doc_count_row).encode('utf-8'))
        if diff_count:
            highlighted = _highlight("{:^83}".format('{} diffs ({} docs)'.format(diff_count, num_docs_with_diffs)))
            print(highlighted.encode('utf-8'))

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


def _blow_away_migration(domain, dst_domain):
    if domain == dst_domain:
        assert not should_use_sql_backend(domain)
        delete_attachments = False
    else:
        revert_form_attachment_meta_domain(domain)
        delete_attachments = True

    delete_diff_db(domain)

    for doc_type in doc_types():
        sql_form_ids = FormAccessorSQL.get_form_ids_in_domain_by_type(dst_domain, doc_type)
        FormAccessorSQL.hard_delete_forms(dst_domain, sql_form_ids, delete_attachments=delete_attachments)

    sql_form_ids = FormAccessorSQL.get_deleted_form_ids_in_domain(dst_domain)
    FormAccessorSQL.hard_delete_forms(dst_domain, sql_form_ids, delete_attachments=delete_attachments)

    sql_case_ids = CaseAccessorSQL.get_case_ids_in_domain(dst_domain)
    CaseAccessorSQL.hard_delete_cases(dst_domain, sql_case_ids)

    sql_case_ids = CaseAccessorSQL.get_deleted_case_ids_in_domain(dst_domain)
    CaseAccessorSQL.hard_delete_cases(dst_domain, sql_case_ids)
    log.info("blew away migration for domain {}\n".format(domain))


def _commit_src_domain(domain):
    """
    Form IDs are the same in both `domain` and `dst_domain`.
    We must delete the form.xml attachments in `domain` so
    that they are not returned by BlobMeta.get_for_parent(),
    BlobMeta.get_for_parents(), and
    BlobMeta.get(parent_id, type_code, name) when called for
    forms in `dst_domain`.
    """
    blob_db = get_blob_db()

    # Prevent any more changes on the Couch domain:
    toggles.DATA_MIGRATION.enable(domain)
    set_couch_sql_migration_not_started(domain)
    for form in _iter_couch_forms(domain):
        for meta in blob_db.metadb.get_for_parent(
            parent_id=form.form_id,
            type_code=CODES.form_xml,
        ):
            # `get_for_parent()` will return meta for both `domain`
            # and `dst_domain` forms. Don't delete the wrong forms.
            if meta.domain == domain:
                blob_db.delete(key=meta.key)
                meta.delete()


def _commit_dst_domain(domain):
    """
    Send forms and cases to ElasticSearch
    """
    # We will be migrating to this domain several times:
    set_couch_sql_migration_not_started(domain)
    for form in _iter_sql_forms(domain):
        publish_form_saved(form)
    for case in _iter_sql_cases(domain):
        publish_case_saved(case, send_post_save_signal=True)


def _iter_couch_forms(domain):
    for doc_type, class_ in six.iteritems(doc_types()):
        form_ids = set(get_form_ids_by_type(domain, doc_type))
        for form in iter_docs(XFormInstance.get_db(), form_ids):
            yield class_.wrap(form)


def _iter_sql_forms(domain):
    for doc_type in doc_types():
        form_ids = FormAccessorSQL.get_form_ids_in_domain_by_type(domain, doc_type)
        for form_ids_chunk in chunked(form_ids, 500):
            for form in FormAccessorSQL.get_forms(list(form_ids_chunk)):
                yield form


def _iter_sql_cases(domain):
    for get_case_ids_func in [
        CaseAccessorSQL.get_case_ids_in_domain,
        CaseAccessorSQL.get_deleted_case_ids_in_domain
    ]:
        case_ids = get_case_ids_func(domain)
        for case_ids_chunk in chunked(case_ids, 500):
            for case in CaseAccessorSQL.get_cases(list(case_ids_chunk)):
                yield case
