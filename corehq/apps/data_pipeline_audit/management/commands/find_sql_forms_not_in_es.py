from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from __future__ import print_function
from datetime import datetime, timedelta
import sys

DATE_FORMAT = "%Y-%m-%d"


def valid_date(s):
    try:
        return datetime.strptime(s, DATE_FORMAT)
    except ValueError:
        msg = "Not a valid date: '{0}'.".format(s)
        raise argparse.ArgumentTypeError(msg)


class Command(BaseCommand):
    help = "Print IDs of sql forms that are in the primary DB but not in ES."

    def add_arguments(self, parser):
        parser.add_argument(
            '-s',
            '--startdate',
            dest='start',
            type=valid_date,
            help="The start date. Only applicable to forms on SQL domains. - format YYYY-MM-DD",
        )
        parser.add_argument(
            '-e',
            '--enddate',
            dest='end',
            type=valid_date,
            help="The end date. Only applicable to forms on SQL domains. - format YYYY-MM-DD",
        )

    def handle(self, domain, doc_type, **options):
        startdate = options.get('start')
        enddate = options.get('end')
        print("Fetching all form ids...", file=sys.stderr)
        all_ids = iter_form_ids_by_last_modified(valid_date(startdate), valid_date(enddate))
        print("Woo! Done fetching. Here we go", file=sys.stderr)
        for doc_ids in chunked(all_ids, 500):
            missing_ids = (
                set(doc_ids) -
                set(FormES().size(1).doc_id(doc_ids).values_list('_id', flat=True))
            )
            for form_id in missing_id:
                print(form_id)


def iter_form_ids_by_last_modified(start_datetime, end_datetime):
    from corehq.sql_db.util import run_query_across_partitioned_databases

    annotate = {
        'last_modified': Greatest('received_on', 'edited_on', 'deleted_on'),
    }

    return run_query_across_partitioned_databases(
        XFormInstanceSQL,
        Q(last_modified__gt=start_datetime),
        annotate=annotate,
        values=['form_id'],
    )
