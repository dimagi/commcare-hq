"""
This script prints out the SQL forms that are missing from ES within a
certain date range.

For a full description and suggestions on usage see the original PR
description here: https://github.com/dimagi/commcare-hq/pull/22477

"""

import sys

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.db.models.functions import Greatest

from corehq.util.argparse_types import date_type
from dimagi.utils.chunked import chunked

from corehq.apps.es import FormES
from corehq.form_processor.models import XFormInstance


class Command(BaseCommand):
    help = "Print IDs of sql forms that are in the primary DB but not in ES."

    def add_arguments(self, parser):
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
        startdate = options.get('start')
        enddate = options.get('end')
        print("Fetching all form ids...", file=sys.stderr)
        all_ids = list(form[0] for form in iter_form_ids_by_last_modified(startdate, enddate))
        print("Woo! Done fetching. Here we go", file=sys.stderr)
        for doc_ids in chunked(all_ids, 100):
            es_ids = (FormES()
                      .remove_default_filter('is_xform_instance')
                      .doc_id(doc_ids).values_list('_id', flat=True))
            missing_ids = set(doc_ids) - set(es_ids)
            for form_id in missing_ids:
                print(form_id)


def iter_form_ids_by_last_modified(start_datetime, end_datetime):
    from corehq.sql_db.util import paginate_query_across_partitioned_databases

    annotate = {
        'last_modified': Greatest('received_on', 'edited_on', 'deleted_on'),
    }

    return paginate_query_across_partitioned_databases(
        XFormInstance,
        (Q(last_modified__gt=start_datetime, last_modified__lt=end_datetime)
         & Q(state__in=[XFormInstance.NORMAL, XFormInstance.ARCHIVED])),
        annotate=annotate,
        values=['form_id'],
        load_source='find_sql_forms_not_in_es'
    )
