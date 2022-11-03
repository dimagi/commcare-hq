from django.core.management.base import BaseCommand
from django.db import connections, transaction

CHUNK_SIZE = 500000


class Command(BaseCommand):
    help = "Populate the 'date_last_activity' column in the sms_messagingsubevent table"

    def add_arguments(self, parser):
        parser.add_argument("--chunksize", type=int, default=CHUNK_SIZE)

    def handle(self, **options):
        chunk_size = options["chunk_size"]
        update_subevent_date_from_emails(chunk_size)
        update_subevent_date_from_sms(chunk_size)
        update_subevent_date_from_xform_session(chunk_size)


def update_subevent_date_from_emails(chunk_size):
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
    return run_query_until_no_updates("email", query)


def update_subevent_date_from_sms(chunk_size):
    query = f"""
        update sms_messagingsubevent set date_last_activity = greatest(se.date, sms.date, sms.date_modified)
        from sms_messagingsubevent se join sms_sms sms on se.id = sms.messaging_subevent_id
        where sms_messagingsubevent.id in (
            select se.id from sms_messagingsubevent se
                join sms_sms sms on se.id = sms.messaging_subevent_id
            where se.date_last_activity is null
            limit {chunk_size}
        )
    """
    return run_query_until_no_updates("sms", query)


def update_subevent_date_from_xform_session(chunk_size):
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
    return run_query_until_no_updates("xform_session", query)


def run_query_until_no_updates(slug, query):
    total_rows = 0
    iterations = 0
    while True:
        with transaction.atomic(using='default'), connections["default"].cursor() as cursor:
            cursor.execute(query)
            rowcount = cursor.rowcount

        total_rows += rowcount
        iterations += 1

        if rowcount == 0:
            break

        print(f"[{slug}] Updated {rowcount} ({total_rows}) subevent rows")

    return total_rows, iterations
