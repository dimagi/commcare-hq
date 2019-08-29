
import argparse
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError

from six.moves import range, zip_longest

from couchforms.models import doc_types

from corehq.apps.change_feed.document_types import CASE_DOC_TYPES
from corehq.apps.data_pipeline_audit.dbacessors import (
    get_es_case_counts,
    get_es_case_ids,
    get_es_case_range,
    get_es_form_ids,
    get_es_user_ids,
    get_primary_db_case_ids,
    get_primary_db_form_ids,
)
from corehq.apps.domain.dbaccessors import get_doc_ids_in_domain_by_class
from corehq.apps.users.dbaccessors.all_commcare_users import (
    get_all_user_ids_by_domain,
    get_mobile_user_ids,
)
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.utils import should_use_sql_backend
from corehq.util.markup import (
    CSVRowFormatter,
    SimpleTableWriter,
    TableRowFormatter,
)

DATE_FORMAT = "%Y-%m-%d"


def valid_date(s):
    try:
        return datetime.strptime(s, DATE_FORMAT)
    except ValueError:
        msg = "Not a valid date: '{0}'.".format(s)
        raise argparse.ArgumentTypeError(msg)


class Command(BaseCommand):
    help = "Print doc IDs that are in the primary DB but not in ES. Use in conjunction with 'raw_doc' view."

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('doc_type')
        parser.add_argument(
            '-s',
            '--startdate',
            dest='start',
            type=valid_date,
            help="The start date. Only applicable to forms and cases on SQL domains. - format YYYY-MM-DD",
        )
        parser.add_argument(
            '-e',
            '--enddate',
            dest='end',
            type=valid_date,
            help="The end date. Only applicable to forms and cases on SQL domains. - format YYYY-MM-DD",
        )
        parser.add_argument('--csv', action='store_true', default=False, dest='csv',
                            help='Write output in CSV format.')

    def handle(self, domain, doc_type, **options):
        csv = options.get('csv')
        startdate = options.get('start')
        enddate = options.get('end')

        form_doc_types = doc_types()

        if startdate or enddate:
            if doc_type in CASE_DOC_TYPES or doc_type in form_doc_types:
                if not should_use_sql_backend(domain):
                    raise CommandError("Date filtering not supported for Couch domains")

        if startdate and enddate and enddate <= startdate:
            raise CommandError("enddate must be after startdate")

        handlers = {
            'CommCareCase': compare_cases,
            'CommCareCase-Deleted': compare_cases,
            'CommCareUser': _compare_users,
            'CommCareUser-Deleted': _compare_users,
            'WebUser': _compare_users,
        }
        handlers.update({doc_type: compare_xforms for doc_type in form_doc_types})
        try:
            primary_count, es_count, primary_only, es_only = handlers[doc_type](domain, doc_type, startdate, enddate)
        except KeyError:
            raise CommandError('Unsupported doc type. Use on of: {}'.format(', '.join(handlers)))

        if csv:
            row_formatter = CSVRowFormatter()
        else:
            row_formatter = TableRowFormatter([50, 50])

        date_range_output = ''
        if startdate or enddate:
            end = (enddate or datetime.utcnow().date()).strftime(DATE_FORMAT)
            start = startdate.strftime(DATE_FORMAT)
            date_range_output = ' (Between {} and {})'.format(start, end)

        print("\nDoc ID analysis for {}{}\n".format(doc_type, date_range_output))

        print("Primary Count: {}".format(primary_count))
        print("ES Count: {}\n".format(es_count))

        writer = SimpleTableWriter(self.stdout, row_formatter)
        writer.write_table(
            ['Only in Primary', 'Only in ES'],
            zip_longest(primary_only, es_only, fillvalue='')
        )


def compare_cases(domain, doc_type, startdate, enddate):
    hundred_thousand = 100000
    case_count = get_es_case_counts(domain, doc_type, startdate, enddate)
    if case_count < hundred_thousand:
        # small enough domain, so lookup diffs in one go
        return _get_diffs(
            get_primary_db_case_ids(domain, doc_type, startdate, enddate),
            get_es_case_ids(domain, doc_type, startdate, enddate)
        )
    # large domain, so break up by month
    startdate, enddate = get_es_case_range(domain)
    primary_count, es_count, primary_ids, es_ids = 0, 0, set(), set()
    months = (enddate - startdate).days / 30 + 1
    for month in range(0, months):
        enddate = (startdate + timedelta(days=(month + 1) * 30)).date()
        startdate = (startdate + timedelta(days=month * 30)).date()
        pc1, esc1, p1, es1 = _get_diffs(
            get_primary_db_case_ids(domain, doc_type, startdate, enddate),
            get_es_case_ids(domain, doc_type, startdate, enddate)
        )
        primary_count = primary_count + pc1
        es_count = es_count + esc1
        primary_ids = primary_ids.union(p1)
        es_ids = es_ids.union(es1)
    return primary_count, es_count, primary_ids, es_ids


def compare_xforms(domain, doc_type, startdate, enddate):
    return _get_diffs(
        get_primary_db_form_ids(domain, doc_type, startdate, enddate),
        get_es_form_ids(domain, doc_type, startdate, enddate)
    )


def _compare_users(domain, doc_type, startdate, enddate):
    if startdate or enddate:
        raise CommandError("Date filtering not supported for users")

    include_web_users = doc_type == 'WebUser'
    if not include_web_users and 'Deleted' in doc_type:
        # deleted users = all users - non-deleted users
        all_mobile_user_ids = set(get_doc_ids_in_domain_by_class(domain, CommCareUser))
        non_deleted_mobile_user_ids = get_mobile_user_ids(domain)
        couch_count = all_mobile_user_ids - non_deleted_mobile_user_ids
    else:
        couch_count = set(get_all_user_ids_by_domain(
            domain,
            include_web_users=include_web_users,
            include_mobile_users=not include_web_users)
        )
    return _get_diffs(
        couch_count,
        get_es_user_ids(domain, doc_type)
    )


def _get_diffs(primary_ids, es_ids):
    return len(primary_ids), len(es_ids), primary_ids - es_ids, es_ids - primary_ids
