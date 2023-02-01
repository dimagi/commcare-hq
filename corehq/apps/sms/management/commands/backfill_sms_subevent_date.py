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

CHUNK_SIZE = 100000

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
        # this one must always run after all the other date back-filling
        update_subevent_date_from_subevent(chunk_size, explain)

        # back-fill domain
        update_subevent_domain_from_parent(chunk_size, explain)

        if not explain:
            try:
                set_migration_complete(ALL_DOMAINS, MIGRATION_SLUG)
            except DomainMigrationProgressError:
                if not force:
                    raise


def update_subevent_date_from_emails(chunk_size, explain):
    count_query = """
        select count(*) from sms_messagingsubevent se
            join sms_email em on se.id = em.messaging_subevent_id
        where se.date_last_activity is null
    """

    query = f"""
        update sms_messagingsubevent set date_last_activity = greatest(
            sms_messagingsubevent.date, em.date, em.date_modified
        )
        from sms_email em where sms_messagingsubevent.id = em.messaging_subevent_id
        and sms_messagingsubevent.id in (
            select se.id from sms_messagingsubevent se
                join sms_email em on se.id = em.messaging_subevent_id
            where se.date_last_activity is null
            limit {chunk_size}
        )
    """
    return run_query_until_no_updates("email", query, count_query, explain)


def update_subevent_date_from_sms(chunk_size, explain):
    count_query = """
        select count(*) from sms_messagingsubevent se
            join sms_sms sms on se.id = sms.messaging_subevent_id
        where se.date_last_activity is null
    """
    query = f"""
        update sms_messagingsubevent set date_last_activity = greatest(
            sms_messagingsubevent.date, sms.date, sms.date_modified
        )
        from sms_sms sms where sms_messagingsubevent.id = sms.messaging_subevent_id
        and sms_messagingsubevent.id in (
            select se.id from sms_messagingsubevent se
                join sms_sms sms on se.id = sms.messaging_subevent_id
            where se.date_last_activity is null
            limit {chunk_size}
        )
    """
    return run_query_until_no_updates("sms", query, count_query, explain)


def update_subevent_date_from_xform_session(chunk_size, explain):
    count_query = """
        select count(*) from sms_messagingsubevent where
        sms_messagingsubevent.xforms_session_id is not null
        and sms_messagingsubevent.date_last_activity is null
    """
    query = f"""
        update sms_messagingsubevent set date_last_activity = greatest(
            sms_messagingsubevent.date, sess.modified_time
        )
        from smsforms_sqlxformssession sess where sms_messagingsubevent.xforms_session_id = sess.id
        and sms_messagingsubevent.id in (
            select id from sms_messagingsubevent where
            sms_messagingsubevent.xforms_session_id is not null
            and sms_messagingsubevent.date_last_activity is null
            limit {chunk_size}
        )
    """
    return run_query_until_no_updates("xform_session", query, count_query, explain)


def update_subevent_date_from_subevent(chunk_size, explain):
    """This updates all remaining events that haven't had a date populated.
    The majority of these represent errors, but I've found that there are
    a number of places in code where a message is updated in code without
    being saved to the DB immediately which leaves scope for the message never
    being updated.
    """
    # this count will only be correct after the other backfills have run
    count_query = """
        select count(*) from sms_messagingsubevent where date_last_activity is null
    """
    query = f"""
        update sms_messagingsubevent set date_last_activity = sms_messagingsubevent.date
        where sms_messagingsubevent.id in (
            select se.id from sms_messagingsubevent se where se.date_last_activity is null
            limit {chunk_size}
        )
    """
    return run_query_until_no_updates("subevent", query, count_query, explain)


def update_subevent_domain_from_parent(chunk_size, explain):
    count_query = "select count(*) from sms_messagingsubevent where domain is null"

    query = f"""
        update sms_messagingsubevent set domain = parent.domain
        from sms_messagingevent parent where sms_messagingsubevent.parent_id = parent.id
        and sms_messagingsubevent.id in (
            select id from sms_messagingsubevent where
            sms_messagingsubevent.domain is null
            limit {chunk_size}
        )
    """
    return run_query_until_no_updates("domain", query, count_query, explain)


def run_query_until_no_updates(slug, query, count_query, explain):
    if explain:
        explain_query_until_no_updates(slug, query, count_query)
        return 0, 0

    return run_query_until_no_updates_(slug, query, count_query)


def run_query_until_no_updates_(slug, query, count_query):
    total_rows_updated = 0
    iterations = 0

    total_rows = _get_count(count_query)

    if total_rows == 0:
        print(f"Skipping backfill for '{slug}', no rows to update.")
        return

    print(f"Running backfill for '{slug}' query. {total_rows} rows to update")

    while True:
        with transaction.atomic(using='default'), connections["default"].cursor() as cursor:
            cursor.execute(query)
            rowcount = cursor.rowcount

        total_rows_updated += rowcount
        iterations += 1

        if rowcount != 0 or total_rows_updated == 0:
            print(f"  [{slug}] Updated {total_rows_updated} of {total_rows} rows")

        if rowcount == 0:
            break

    return total_rows_updated, iterations


def _get_count(count_query):
    with connections["default"].cursor() as cursor:
        cursor.execute(count_query)
        total_rows = cursor.fetchone()[0]
    return total_rows


def explain_query_until_no_updates(slug, query, count_query):
    total_rows = _get_count(count_query)
    print(f"Running 'explain' for {slug} query: total rows to update = {total_rows}\n")
    query = f"explain {query}"
    with transaction.atomic(using='default'), connections["default"].cursor() as cursor:
        cursor.execute(query)
        for row in cursor.fetchall():
            print(row)
        print()
