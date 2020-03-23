"""
This script prints out the SQL forms that are missing from ES within a
certain date range.

For a full description and suggestions on usage see the original PR
description here: https://github.com/dimagi/commcare-hq/pull/22477

"""

import sys
from collections import namedtuple

from django.core.management.base import BaseCommand
from django.db.models import F, Q
from django.db.models.functions import Greatest

from corehq.util.argparse_types import date_type
from dimagi.utils.chunked import chunked

from corehq.apps.es import FormES
from corehq.form_processor.models import XFormInstanceSQL


class Command(BaseCommand):
    help = "Print IDs and info of sql forms that are in the primary DB but not in ES."

    def add_arguments(self, parser):
        parser.add_argument(
            '-d',
            '--domain',
            dest='domain',
            help="Filter by this domain (optional)",
        )
        parser.add_argument(
            '-s',
            '--startdate',
            dest='start',
            type=date_type,
            help="The start date. Only applicable to forms on SQL domains. - format YYYY-MM-DD",
        )
        parser.add_argument(
            '-e',
            '--enddate',
            dest='end',
            type=date_type,
            help="The end date. Only applicable to forms on SQL domains. - format YYYY-MM-DD",
        )

    def handle(self, **options):
        domain = options.get('domain')
        startdate = options.get('start')
        enddate = options.get('end')
        print("Fetching all form ids...", file=sys.stderr)
        print("Woo! Done fetching. Here we go", file=sys.stderr)
        print('Form ID\tLast Modified\tDomain')
        for chunk in chunked(iter_form_ids_by_last_modified(domain, startdate, enddate), 100):
            info_by_id = {f.form_id: f for f in chunk}
            doc_ids = list(info_by_id.keys())

            es_ids = (FormES()
                      .remove_default_filters()
                      .doc_id(doc_ids).values_list('_id', flat=True))
            missing_ids = set(doc_ids) - set(es_ids)
            for form_id in missing_ids:
                info = info_by_id[form_id]
                print(f'{info.form_id}\t{info.last_modified}\t{info.domain}')


def iter_form_ids_by_last_modified(domain, start_datetime, end_datetime):
    from corehq.sql_db.util import paginate_query_across_partitioned_databases

    annotate = {
        'last_modified': Greatest('received_on', 'edited_on', 'deleted_on'),
    }

    q_kwargs = {}
    if domain:
        q_kwargs['domain'] = domain
    if start_datetime:
        q_kwargs['last_modified__gt'] = start_datetime
    if end_datetime:
        q_kwargs['last_modified__lt'] = end_datetime

    for row in paginate_query_across_partitioned_databases(
        XFormInstanceSQL,
        (Q(**q_kwargs) &
         Q(state=F('state').bitand(XFormInstanceSQL.DELETED) +
            F('state').bitand(XFormInstanceSQL.DEPRECATED) +
            F('state').bitand(XFormInstanceSQL.DUPLICATE) +
            F('state').bitand(XFormInstanceSQL.ERROR) +
            F('state').bitand(XFormInstanceSQL.SUBMISSION_ERROR_LOG) +
            F('state'))),
        annotate=annotate,
        values=['form_id', 'last_modified', 'domain'],
        load_source='find_sql_forms_not_in_es'
    ):
        yield FormResult(*row)


FormResult = namedtuple('FormResult', 'form_id, last_modified, domain')
