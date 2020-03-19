import logging
import os

from django.core.management.base import BaseCommand, CommandError

from dimagi.utils.chunked import chunked

from corehq.apps.domain.models import Domain
from corehq.form_processor.backends.sql.dbaccessors import (
    CaseAccessorSQL,
    FormAccessorSQL,
)
from corehq.form_processor.models import (
    CaseTransaction,
    CommCareCaseSQL,
    RebuildWithReason,
)
from corehq.form_processor.utils import should_use_sql_backend
from corehq.sql_db.util import get_db_aliases_for_partitioned_query

from ...couchsqlmigration import setup_logging
from ...rebuildcase import SortTransactionsRebuild, rebuild_case

log = logging.getLogger(__name__)

PENDING_WARNING = "Diffs pending. Run again with --cases=pending"


class Command(BaseCommand):
    help = "Revert SQL case transactions to standard server-date ordering"

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('--debug', action='store_true', default=False)
        parser.add_argument('--commit',
            dest="commit", action='store_true', default=False,
            help="Write changes in addition to showing diffs.")
        parser.add_argument('--state-dir',
            default=os.environ.get("CCHQ_MIGRATION_STATE_DIR"),
            required="CCHQ_MIGRATION_STATE_DIR" not in os.environ,
            help="""
                Directory for couch2sql logs and migration state. This must not
                reside on an NFS volume for migration state consistency.
                Can be set in environment: CCHQ_MIGRATION_STATE_DIR
            """)

    def handle(self, domain, *, state_dir, commit, debug, **options):
        if not should_use_sql_backend(domain):
            raise CommandError(f'Cannot unsort commits on couch domain: {domain}')

        assert Domain.get_by_name(domain), f'Unknown domain "{domain}"'
        setup_logging(state_dir, "unsort_sql_cases", debug)

        if commit:
            log.info("COMMIT MODE: show and save unsorted transactions...")
        else:
            log.info("DRY RUN: show but do not save unsorted transactions...")
        case_ids = iter_sql_cases_with_sorted_transactions(domain)
        for batch in chunked(case_ids, 100, list):
            for sql_case in CaseAccessorSQL.get_cases(batch):
                unsort_transactions(sql_case, commit)


def iter_sql_cases_with_sorted_transactions(domain):
    sql = f"""
        SELECT cx.case_id
        FROM {CommCareCaseSQL._meta.db_table} cx
        INNER JOIN {CaseTransaction._meta.db_table} tx ON cx.case_id = tx.case_id
        WHERE cx.domain = %s AND tx.details LIKE %s
    """
    reason = f'%{SortTransactionsRebuild._REASON}%'
    for dbname in get_db_aliases_for_partitioned_query():
        with CommCareCaseSQL.get_cursor_for_partition_db(dbname) as cursor:
            cursor.execute(sql, [domain, reason])
            yield from iter(set(case_id for case_id, in cursor.fetchall()))


def unsort_transactions(sql_case, commit):
    rebuilds = [t for t in sql_case.transactions if is_rebuild(t)]
    others = [t for t in sql_case.transactions if not is_rebuild(t)]
    assert len(rebuilds) == 1, rebuilds
    changes = []
    for trans in sorted(others, key=lambda t: t.server_date):
        if not trans.form_id:
            continue
        received_on = FormAccessorSQL.get_form(trans.form_id).received_on
        if received_on != trans.server_date:
            changes.append((trans, received_on))
            if commit:
                trans.server_date = received_on
                trans.save()
    case_id = sql_case.case_id
    if changes:
        chg = "\n".join(
            f"  {t.form_id}: {t.server_date} -> {received_on}"
            for t, received_on in changes
        )
        log.info("unsort transactions for case %s:\n%s", case_id, chg)
        if commit:
            detail = RebuildWithReason(reason=UNSORT_REBUILD_REASON)
            rebuild_case(sql_case, detail)
    else:
        log.info("no changes for case %s", case_id)


def is_rebuild(trans):
    return (trans.details
        and trans.details["reason"] == SortTransactionsRebuild._REASON)


UNSORT_REBUILD_REASON = "Couch to SQL: unsort transactions"
