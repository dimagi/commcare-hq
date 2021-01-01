import csv
import datetime
from contextlib import contextmanager
from inspect import cleandoc

from django.core.management.base import BaseCommand

from corehq.motech.repeaters.const import (
    RECORD_CANCELLED_STATE,
    RECORD_SUCCESS_STATE,
)
from corehq.motech.repeaters.dbaccessors import (
    iter_sql_repeat_records_by_domain,
)
from corehq.motech.repeaters.models import Repeater


class Command(BaseCommand):
    help = cleandoc("""
    If there are multiple cancelled repeat records for a given payload id, this
    will delete all but one for each payload, reducing the number of requests
    that must be made. It will also delete any cancelled repeat records for
    which there is a more recent successful record with the same payload_id.
    """)

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('repeater_id')

    def handle(self, domain, repeater_id, *args, **options):
        # This differs from the original code as follows:
        # 1. It does not prompt for confirmation
        # 2. If a successful record has been resent, and that resent
        #    record is cancelled, this function will keep the most
        #    recent (cancelled) record and delete the older (successful)
        #    record. The original code would keep the successful record
        #    and delete the cancelled record. One could argue for both
        #    approaches. The current behaviour respects the decision to
        #    resend the successful payload.

        records, __ = iter_sql_repeat_records_by_domain(
            domain,
            repeater_id,
            states=[RECORD_SUCCESS_STATE, RECORD_CANCELLED_STATE],
            order_by=['payload_id', '-registered_at'],
        )
        last_payload_id = None
        with csv_log_writer(domain, repeater_id) as writer:
            for record in records:
                if record.payload_id != last_payload_id:
                    last_payload_id = record.payload_id
                    succeeded = record.state == RECORD_SUCCESS_STATE
                    writer.writerow(get_latest_record_row(record))
                    continue
                writer.writerow(get_duplicate_record_row(record, succeeded))
                record.delete()


@contextmanager
def csv_log_writer(domain, repeater_id):
    repeater = Repeater.get(repeater_id)
    assert repeater.domain == domain
    filename = "cancelled_{}_records-{}.csv".format(
        repeater.__class__.__name__,
        datetime.datetime.utcnow().isoformat())
    print("Writing log of changes to {}".format(filename))
    with open(filename, 'w', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow((
            'RepeatRecord ID',
            'Payload ID',
            'Failure Reason',
            'Deleted?',
            'Reason',
        ))
        yield writer


def get_latest_record_row(record):
    if record.state == RECORD_CANCELLED_STATE:
        failure_reason = list(record.attempts)[-1].message
    else:
        failure_reason = ''
    return (
        record.pk,
        record.payload_id,
        failure_reason,
        'No',
        '',
    )


def get_duplicate_record_row(record, succeeded):
    if record.state == RECORD_CANCELLED_STATE:
        failure_reason = list(record.attempts)[-1].message
    else:
        failure_reason = ''
    return (
        record.pk,
        record.payload_id,
        failure_reason,
        'Yes',
        'Already Sent' if succeeded else 'Duplicate',
    )
