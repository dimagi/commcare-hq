from django.core.management.base import BaseCommand
from django.db import connections, transaction

from corehq.apps.domain_migration_flags.api import (
    ALL_DOMAINS,
    get_migration_status,
    set_migration_complete,
    set_migration_started,
)
from corehq.apps.domain_migration_flags.exceptions import (
    DomainMigrationProgressError,
)
from corehq.apps.domain_migration_flags.models import MigrationStatus

CHUNK_SIZE = 500000

MIGRATION_SLUG = "sms_messagingsubevent_date_last_activity_backfill"


class Command(BaseCommand):
    help = "Populate the 'date_last_activity' column in the sms_messagingsubevent table"

    def add_arguments(self, parser):
        parser.add_argument("--chunksize", type=int, default=CHUNK_SIZE)
        parser.add_argument("--explain", action="store_true", default=False)
        parser.add_argument("--force", action="store_true", default=False,
                            help="Run the queries even if the migration has been marked complete.")

    def handle(self, **options):
        explain = options["explain"]
        force = options["force"]
        if not explain:
            status = get_migration_status(ALL_DOMAINS, MIGRATION_SLUG)
            if status == MigrationStatus.COMPLETE and not force:
                print("Backfill has already been marked as complete")
                return

            if status not in (MigrationStatus.IN_PROGRESS, MigrationStatus.COMPLETE):
                set_migration_started(ALL_DOMAINS, MIGRATION_SLUG)

        chunk_size = options["chunksize"]
        update_subevent_date_from_emails(chunk_size, explain)
        update_subevent_date_from_sms(chunk_size, explain)
        update_subevent_date_from_xform_session(chunk_size, explain)

        if not explain:
            try:
                set_migration_complete(ALL_DOMAINS, MIGRATION_SLUG)
            except DomainMigrationProgressError:
                if not force:
                    raise


def update_subevent_date_from_emails(chunk_size, explain):
    query = f"""
        update sms_messagingsubevent set date_last_activity = greatest(se.date, em.date, em.date_modified)
        from sms_messagingsubevent se join sms_email em on se.id = em.messaging_subevent_id
        where sms_messagingsubevent.id in (
            select se.id from sms_messagingsubevent se
                join sms_email em on se.id = em.messaging_subevent_id
            where se.date_last_activity is null
            limit {chunk_size}
        )
    """
    return run_query_until_no_updates("email", query, explain)


def update_subevent_date_from_sms(chunk_size, explain):
    query = f"""
        update sms_messagingsubevent set date_last_activity = greatest(se.date, sms.date, sms.date_modified)
        from sms_messagingsubevent se join sms_sms sms on se.id = sms.messaging_subevent_id
        where sms_messagingsubevent.id in (
            select count(*) from sms_messagingsubevent se
                join sms_sms sms on se.id = sms.messaging_subevent_id
            where se.date_last_activity is null
            limit {chunk_size}
        )
    """
    return run_query_until_no_updates("sms", query, explain)


def update_subevent_date_from_xform_session(chunk_size, explain):
    query = f"""
        update sms_messagingsubevent set date_last_activity = greatest(se.date, sess.modified_time)
        from sms_messagingsubevent se join smsforms_sqlxformssession sess on se.xforms_session_id = sess.id
        where sms_messagingsubevent.id in (
            select id from sms_messagingsubevent where
            sms_messagingsubevent.xforms_session_id is not null
            and sms_messagingsubevent.date_last_activity is null
            limit {chunk_size}
        )
    """
    return run_query_until_no_updates("xform_session", query, explain)


def run_query_until_no_updates(slug, query, explain):
    total_rows = 0
    iterations = 0
    if explain:
        print(f"Running 'explain' for {slug} query:\n")
        query = f"explain {query}"
    else:
        print(f"Running backfill for {slug} query:\n")
    while True:
        with transaction.atomic(using='default'), connections["default"].cursor() as cursor:
            cursor.execute(query)
            rowcount = cursor.rowcount
            if explain:
                for row in cursor.fetchall():
                    print(row)
                print()
                return

        total_rows += rowcount
        iterations += 1

        print(f"[{slug}] Updated {rowcount} ({total_rows}) subevent rows")

        if rowcount == 0:
            break

    return total_rows, iterations
