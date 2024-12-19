import csv
import datetime
from collections import defaultdict

from django.core.management.base import BaseCommand

from memoized import memoized

from corehq.motech.repeaters.const import (
    RECORD_CANCELLED_STATE,
    RECORD_SUCCESS_STATE,
)
from corehq.motech.repeaters.models import Repeater, RepeatRecord


class Command(BaseCommand):
    help = """
    If there are multiple cancelled repeat records for a given payload id, this
    will delete all but one for each payload, reducing the number of requests
    that must be made. It will also delete any cancelled repeat records for
    which there is a more recent successful record with the same payload_id.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            'domain',
        )
        parser.add_argument(
            'repeater_id',
        )

    @property
    @memoized
    def most_recent_success(self):
        res = {}
        for record in RepeatRecord.objects.iterate(
                self.domain, repeater_id=self.repeater_id, state=RECORD_SUCCESS_STATE):
            if record.last_checked:
                res[record.payload_id] = max(res.get(record.payload_id, datetime.datetime.min),
                                             record.last_checked)
        return res

    def handle(self, domain, repeater_id, *args, **options):
        self.domain = domain
        self.repeater_id = repeater_id
        repeater = Repeater.objects.get(id=repeater_id)
        print("Looking up repeat records for '{}'".format(repeater.friendly_name))

        redundant_records = []
        records_by_payload_id = defaultdict(list)
        records = RepeatRecord.objects.iterate(domain, repeater_id=repeater_id, state=RECORD_CANCELLED_STATE)
        total_records = 0
        for record in records:
            total_records += 1
            most_recent_success = self.most_recent_success.get(record.payload_id)
            if most_recent_success and record.last_checked < most_recent_success:
                # another record with this payload has succeeded after this record failed
                redundant_records.append(record)
            else:
                records_by_payload_id[record.payload_id].append(record)

        unique_payloads = len(records_by_payload_id)
        redundant_payloads = len(redundant_records)
        print("There are {total} total cancelled records, {redundant} with payloads which "
              "have since succeeded, and {unique} unsent unique payload ids."
              .format(total=total_records,
                      redundant=redundant_payloads,
                      unique=unique_payloads))
        print("Delete {} duplicate records?".format(total_records - unique_payloads))
        if not input("(y/n)") == 'y':
            print("Aborting")
            return

        redundant_log = self.delete_already_successful_records(redundant_records)
        duplicates_log = self.resolve_duplicates(records_by_payload_id)

        filename = "cancelled_{}_records-{}.csv".format(
            repeater._repeater_type,
            datetime.datetime.utcnow().isoformat())
        print("Writing log of changes to {}".format(filename))
        with open(filename, 'w', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(('RepeatRecord ID', 'Payload ID', 'Failure Reason', 'Deleted?', 'Reason'))
            writer.writerows(redundant_log)
            writer.writerows(duplicates_log)

    def resolve_duplicates(self, records_by_payload_id):
        log = []
        with RepeatRecordDeleter() as iter_db:
            for payload_id, records in records_by_payload_id.items():
                log.append((records[0].id, payload_id, records[0].failure_reason, 'No', ''))
                if len(records) > 1:
                    for record in records[1:]:
                        iter_db.delete(record)
                        log.append((record.id, payload_id, record.failure_reason, 'Yes', 'Duplicate'))
        return log

    def delete_already_successful_records(self, redundant_records):
        log = []
        with RepeatRecordDeleter() as iter_db:
            for record in redundant_records:
                iter_db.delete(record)
                log.append((record.id, record.payload_id, record.failure_reason, 'Yes', 'Already Sent'))
        return log


class RepeatRecordDeleter:

    def __enter__(self):
        self.ids_to_delete = []
        return self

    def delete(self, record):
        self.ids_to_delete.append(record.id)
        if len(self.ids_to_delete) > 100:
            self.flush()

    def flush(self):
        if self.ids_to_delete:
            RepeatRecord.objects.filter(id__in=self.ids_to_delete).delete()
            self.ids_to_delete = []

    def __exit__(self, *exc_info):
        self.flush()
        del self.ids_to_delete
