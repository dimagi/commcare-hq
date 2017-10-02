import csv
import datetime
import re
import time

from django.core.management.base import BaseCommand

from corehq.motech.repeaters.const import RECORD_CANCELLED_STATE
from corehq.motech.repeaters.dbaccessors import iter_repeat_records_by_domain


class Command(BaseCommand):
    help = """
    Send cancelled repeat records. You may optionally specify a regex to
    filter records using --include or --exclude, an a sleep time with --sleep
    """

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('repeater_id')
        parser.add_argument(
            '--include',
            dest='include_regex',
            help=("Regex that will be applied to a record's 'failure_reason' to "
                  "determine whether to include it."),
        )
        parser.add_argument(
            '--exclude',
            dest='exclude_regex',
            help=("Regex that will be applied to a record's 'failure_reason' to "
                  "determine whether to exclude it."),
        )
        parser.add_argument(
            '--sleep',
            dest='sleep_time',
            help="Time in seconds to sleep between each request.",
        )
        parser.add_argument(
            '--verbose',
            dest='verbose',
            action='store_true',
            default=False,
            help="Print out all matching failure reasons",
        )

    def handle(self, domain, repeater_id, *args, **options):
        sleep_time = options.get('sleep_time')
        include_regex = options.get('include_regex')
        exclude_regex = options.get('exclude_regex')
        verbose = options.get('verbose')
        if include_regex and exclude_regex:
            print "You may not specify both include and exclude"

        def meets_filter(record):
            if include_regex:
                if not record.failure_reason:
                    return False
                return bool(re.search(include_regex, record.failure_reason))
            elif exclude_regex:
                if not record.failure_reason:
                    return True
                return not bool(re.search(exclude_regex, record.failure_reason))
            return True  # No filter applied

        records = filter(
            meets_filter,
            iter_repeat_records_by_domain(domain, repeater_id=repeater_id, state=RECORD_CANCELLED_STATE)
        )

        if verbose:
            for record in records:
                print record.payload_id, record.failure_reason

        total_records = len(records)
        print "Found {} matching records.  Send them?".format(total_records)
        if not raw_input("(y/n)") == 'y':
            print "Aborting"
            return

        filename = "sent_repeat_records-{}.csv".format(
            datetime.datetime.utcnow().strftime('%Y-%m-%d_%H.%M.%S'))
        with open(filename, 'w') as f:
            writer = csv.writer(f)
            writer.writerow(('record_id', 'payload_id', 'state', 'failure_reason'))

            for i, record in enumerate(records):
                try:
                    if record.next_check is None:
                        record.next_check = datetime.datetime.utcnow()
                    record.fire(force_send=True)
                except Exception as e:
                    print "{}/{}: {} {}".format(i, total_records, 'EXCEPTION', repr(e))
                    writer.writerow((record._id, record.payload_id, record.state, repr(e)))
                else:
                    print "{}/{}: {}".format(i, total_records, record.state)
                    writer.writerow((record._id, record.payload_id, record.state, record.failure_reason))
                if sleep_time:
                    time.sleep(float(sleep_time))

        print "Wrote log of changes to {}".format(filename)
