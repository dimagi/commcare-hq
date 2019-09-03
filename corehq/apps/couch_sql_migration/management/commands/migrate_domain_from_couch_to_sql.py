import logging
import os
import sys
from itertools import groupby, zip_longest

import six
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from six.moves import input, zip_longest
from sqlalchemy.exc import OperationalError

from corehq.apps.domain.models import Domain
from corehq.blobs import get_blob_db, CODES
from corehq.form_processor.change_publishers import publish_case_saved, publish_form_saved
from couchforms.dbaccessors import get_form_ids_by_type
from couchforms.models import XFormInstance, doc_types

from corehq import toggles
from sqlalchemy.exc import OperationalError

from couchforms.dbaccessors import get_form_ids_by_type
from couchforms.models import XFormInstance, doc_types

from corehq.apps.couch_sql_migration.couchsqlmigration import (
    CASE_DOC_TYPES,
    do_couch_to_sql_migration,
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
from corehq.apps.couch_sql_migration.statedb import (
    Counts,
    delete_state_db,
    open_state_db,
)
from corehq.apps.domain.dbaccessors import get_doc_ids_in_domain_by_type
from corehq.apps.hqcase.dbaccessors import get_case_ids_in_domain
from corehq.form_processor.backends.sql.dbaccessors import (
    CaseAccessorSQL,
    FormAccessorSQL,
)
from corehq.form_processor.utils import should_use_sql_backend
from corehq.util.markup import shell_green, shell_red
from dimagi.utils.chunked import chunked

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
        parser.add_argument('--dest')
        parser.add_argument('--no-input', action='store_true', default=False)
        parser.add_argument('--debug', action='store_true', default=False)
        parser.add_argument('--verbose', action='store_true', default=False,
            help="Show verbose stats output.")
        parser.add_argument('--state-dir',
            default=os.environ.get("CCHQ_MIGRATION_STATE_DIR"),
            required="CCHQ_MIGRATION_STATE_DIR" not in os.environ,
            help="""
                Directory for couch2sql logs and migration state. This must not
                reside on an NFS volume for migration state consistency.
                Can be set in environment: CCHQ_MIGRATION_STATE_DIR
            """)
        parser.add_argument('--live',
            dest="live_migrate", action='store_true', default=False,
            help='''
                Do migration in a way that will not be seen by
                `any_migrations_in_progress(...)` so it does not block
                operations like syncs, form submissions, sms activity,
                etc. A "live" migration will stop when it encounters a
                form that has been submitted within an hour of the
                current time. Live migrations can be resumed after
                interruption or to top off a previous live migration by
                processing unmigrated forms that are older than one
                hour. Migration state must be present in the state
                directory to resume. A live migration may be followed by
                a normal (non-live) migration, which will commit the
                result if all goes well.
            ''')
        parser.add_argument('--dry-run', action='store_true', default=False,
            help="""
                A "dry run" migration tests the migration process, but
                does not migrate form attachments if the destination
                domain is different from the source domain. Diffs will
                be calculated and errors reported. Like a "live"
                migration, normal activity on the domain is not blocked.
            """
        )
        parser.add_argument('--no-diff-process',
            dest='diff_process', action='store_false', default=True,
            help='''
                Migrate forms and diff cases in the same process. The
                case diff queue will run in a separate process if this
                option is not specified.
            ''')

    def handle(self, domain, action, **options):
        if should_use_sql_backend(domain):
            raise CommandError(f'It looks like {domain} has already been migrated.')

        for opt in ["no_input", "debug", "verbose", "state_dir", "dry_run", "live_migrate", "diff_process"]:
            setattr(self, opt, options[opt])

        if self.no_input and not settings.UNIT_TESTING:
            raise CommandError('--no-input only allowed for unit testing')

        if action != MIGRATE and self.dry_run:
            raise CommandError("--dry-run only allowed with `MIGRATE`")
        if action != MIGRATE and self.live_migrate:
            raise CommandError("--live only allowed with `MIGRATE`")
        if action != STATS and self.verbose:
            raise CommandError("--verbose only allowed for `stats`")

        dst_domain = options.pop('dest', None) or domain
        assert Domain.get_by_name(domain)
        if domain != dst_domain:
            assert Domain.get_by_name(dst_domain)
        setup_logging(self.state_dir, options['debug'])
        getattr(self, "do_" + action)(domain, dst_domain)

    def do_MIGRATE(self, domain, dst_domain):
        set_couch_sql_migration_started(domain, dry_run=(self.dry_run or self.live_migrate))
        if domain != dst_domain:
            set_couch_sql_migration_started(dst_domain, dry_run=(self.dry_run or self.live_migrate))
        do_couch_to_sql_migration(
            domain,
            self.state_dir,
            dst_domain=dst_domain,
            with_progress=not self.no_input,
            debug=self.debug,
            dry_run=self.dry_run,
            live_migrate=self.live_migrate,
            diff_process=self.diff_process,
        )

        return_code = 0
        if self.live_migrate:
            print("Live migration completed.")
            has_diffs = True
        else:
            has_diffs = self.print_stats(domain, dst_domain, short=True, diffs_only=True)
            return_code = int(has_diffs)
        if has_diffs:
            print("\nRun `diff` or `stats [--verbose]` for more details.\n")
        if return_code:
            sys.exit(return_code)

    def do_reset(self, domain, dst_domain):
        if not self.no_input:
            _confirm(
                "This will delete all SQL forms and cases for the domain "
                f"{dst_domain}. Are you sure you want to continue?"
            )
        set_couch_sql_migration_not_started(domain)
        if domain != dst_domain:
            set_couch_sql_migration_not_started(dst_domain)
        blow_away_migration(domain, dst_domain, self.state_dir)

    def do_COMMIT(self, domain, dst_domain):
        if not couch_sql_migration_in_progress(domain, include_dry_runs=False):
            raise CommandError("cannot commit a migration that is not in state in_progress")
        if not self.no_input:
            _confirm(
                "This will convert the domain to use the SQL backend and"
                "allow new form submissions to be processed. "
                f"Are you sure you want to do this for domain '{domain}'?"
            )
        if domain == dst_domain:
            set_couch_sql_migration_complete(domain)
        else:
            _commit_src_domain(domain)
            _commit_dst_domain(dst_domain)

    def do_stats(self, domain, dst_domain):
        self.print_stats(domain, dst_domain, short=not self.verbose)

    def do_diff(self, domain, dst_domain):
        db = open_state_db(domain, self.state_dir)
        diffs = sorted(db.get_diffs(), key=lambda d: d.kind)
        for doc_type, diffs in groupby(diffs, key=lambda d: d.kind):
            print('-' * 50, f"Diffs for {doc_type}", '-' * 50)
            for diff in diffs:
                print(f'[{doc_type}({diff.doc_id})] {diff.json_diff}')

    def print_stats(self, src_domain, dst_domain, short=True, diffs_only=False):
        status = get_couch_sql_migration_status(src_domain)
        print(f"Couch to SQL migration status for {src_domain}: {status}")
        db = open_state_db(src_domain, self.state_dir)
        try:
            diff_stats = db.get_diff_stats()
        except OperationalError:
            diff_stats = {}

        has_diffs = False
        for doc_type in doc_types():
            form_ids_in_couch = set(get_form_ids_by_type(src_domain, doc_type))
            if doc_type == "XFormInstance":
                form_ids_in_couch.update(get_doc_ids_in_domain_by_type(
                    src_domain, "HQSubmission", XFormInstance.get_db()))
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
            couch_missing_cases = doc_counts.get("CommCareCase-couch", ZERO).missing
        else:
            doc_counts = None
            couch_missing_cases = 0
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
            if doc_type == "CommCareCase" and couch_missing_cases:
                has_diffs = True
                print(shell_red(f"{couch_missing_cases} cases could not be loaded from Couch"))
                if not short:
                    for case_id in db.get_missing_doc_ids("CommCareCase-couch"):
                        print(case_id)

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

        print('\n{:_^79}'.format(f" {name} "))
        print(row.format('Couch', '|', 'SQL'))
        print(_highlight(doc_count_row))
        if diff_count:
            print(_highlight("{:^83}".format(f'{diff_count} diffs ({num_docs_with_diffs} docs)')))

        if not short:
            if ids_in_couch ^ ids_in_sql:
                couch_only = list(ids_in_couch - ids_in_sql)
                sql_only = list(ids_in_sql - ids_in_couch)
                for couch, sql in zip_longest(couch_only, sql_only):
                    print(row.format(couch or '', '|', sql or ''))

        return True


def _confirm(message):
    response = input(f'{message} [y/N]').lower()
    if response != 'y':
        raise CommandError('abort')


def blow_away_migration(domain, dst_domain, state_dir):
    if domain == dst_domain:
        assert not should_use_sql_backend(domain)
        delete_attachments = False
    else:
        revert_form_attachment_meta_domain(domain)
        delete_attachments = True
    delete_state_db(domain, state_dir)

    for doc_type in doc_types():
        sql_form_ids = FormAccessorSQL.get_form_ids_in_domain_by_type(dst_domain, doc_type)
        FormAccessorSQL.hard_delete_forms(dst_domain, sql_form_ids, delete_attachments=delete_attachments)

    sql_form_ids = FormAccessorSQL.get_deleted_form_ids_in_domain(dst_domain)
    FormAccessorSQL.hard_delete_forms(dst_domain, sql_form_ids, delete_attachments=delete_attachments)

    sql_case_ids = CaseAccessorSQL.get_case_ids_in_domain(dst_domain)
    CaseAccessorSQL.hard_delete_cases(dst_domain, sql_case_ids)

    sql_case_ids = CaseAccessorSQL.get_deleted_case_ids_in_domain(dst_domain)
    CaseAccessorSQL.hard_delete_cases(dst_domain, sql_case_ids)
    log.info(f"blew away migration for domain {domain}\n")


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
    toggles.DATA_MIGRATION.set(domain, True)
    set_couch_sql_migration_not_started(domain)
    for form_id in _iter_couch_form_ids(domain):
        metas = blob_db.metadb.get_for_parent(
            parent_id=form_id,
            type_code=CODES.form_xml,
        )
        keys = {meta.key for meta in metas}
        if len(metas) != len(keys):
            print(f'DUPLICATE META KEYS for form {form_id}!')
            log.error(f'DUPLICATE META KEYS for form {form_id}!')
            continue
        for meta in metas:
            # `get_for_parent()` will return meta for both `domain`
            # and `dst_domain` forms. Don't delete the wrong forms.
            if meta.domain == domain:
                blob_db.delete(key=meta.key)


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


def _iter_couch_form_ids(domain):
    for doc_type, class_ in six.iteritems(doc_types()):
        for form_id in get_form_ids_by_type(domain, doc_type):
            yield form_id


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
