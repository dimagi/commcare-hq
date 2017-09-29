import csv
import datetime
from collections import defaultdict

from django.core.management.base import BaseCommand

from corehq.util.couch import IterDB
from corehq.motech.repeaters.const import RECORD_CANCELLED_STATE
from corehq.motech.repeaters.models import RepeatRecord
from corehq.motech.repeaters.dbaccessors import iter_repeat_records_by_domain


class Command(BaseCommand):
    help = """
    If there are multiple cancelled repeat records for a given payload id, this
    will delete all but one for each payload, reducing the number of requests
    that must be made.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            'domain',
        )
        parser.add_argument(
            'repeater_id',
        )

    def handle(self, domain, repeater_id, *args, **options):
        records_by_payload_id = defaultdict(list)
        records = iter_repeat_records_by_domain(domain, repeater_id=repeater_id, state=RECORD_CANCELLED_STATE)
        total_records = 0
        for record in records:
            records_by_payload_id[record.payload_id].append(record)
            total_records += 1

        unique_payloads = len(records_by_payload_id)
        print ("There are {} total records and {} unique payload ids."
               .format(total_records, unique_payloads))
        print "Delete {} duplicate records?".format(total_records - unique_payloads)
        if not raw_input("(y/n)") == 'y':
            print "Aborting"
            return

        log = resolve_duplicates(records_by_payload_id)
        filename = "cancelled_repeat_records-{}.csv".format(datetime.datetime.utcnow().isoformat())
        print "Writing log of changes to {}".format(filename)
        with open(filename, 'w') as f:
            writer = csv.writer(f)
            writer.writerows(log)


def resolve_duplicates(records_by_payload_id):
    log = [('RepeatRecord ID', 'Payload ID', 'Deleted?')]
    with IterDB(RepeatRecord.get_db()) as iter_db:
        for payload_id, records in records_by_payload_id.items():
            log.append((records[0]._id, payload_id, records[0].failure_reason, 'No'))
            if len(records) > 1:
                for record in records[1:]:
                    iter_db.delete(record)
                    log.append((record._id, payload_id, record.failure_reason, 'Yes'))
    return log
