from django.core.management.base import BaseCommand
from corehq.apps.userreports.tasks import _get_config_by_id
from corehq.apps.userreports.util import get_table_name
from corehq.apps.userreports.models import AsyncIndicator
from django.db import connections

from dimagi.utils.chunked import chunked


class Command(BaseCommand):
    help = "Rebuild Bihar person cases (Child and AG Cases)"

    def add_arguments(self, parser):
        parser.add_argument(
            'type_of_cases',
            type=str
        )

    def handle(self, *args, **kwargs):
        # by default execute child cases
        type_of_cases = kwargs['type_of_cases'] if kwargs['type_of_cases'] else "child_cases"
        person_config = _get_config_by_id('static-icds-cas-static-person_cases_v3')
        # sort by supervisor_id and doc_id to improve the performance, sorting is needed to resume the queueing
        # if it fails in between.
        # AG Cases
        query = ""
        if type_of_cases == 'ag_cases':
            # AG CASES
            table_name = get_table_name('icds-cas', 'static-person_cases_v3')
            # includes all the valid cases for the march april and may 2020
            ag_end_range = '2009-06-01'
            ag_start_range = '2006-03-01'
            query = f"""
                select supervisor_id, doc_id from "{table_name}"
                where state_id='f9b47ea2ee2d8a02acddeeb491d3e175' AND sex='F'
                AND dob::DATE>='{ag_start_range}' AND dob::DATE<{ag_end_range}
                order by supervisor_id, doc_id
            """
        else:
            # child cases
            table_name = get_table_name('icds-cas', 'static-child_health_cases')
            query = f"""
                        select supervisor_id, mother_id from "{table_name}"
                        where state_id='f9b47ea2ee2d8a02acddeeb491d3e175'
                        order by supervisor_id, mother_id
                    """
        with connections['icds-ucr-citus'].cursor() as cursor:
            cursor.execute(query)
            doc_ids = cursor.fetchall()

        total_doc_ids = len(doc_ids)
        count = 0
        chunk_size = 10000
        for ids_chunk in chunked(doc_ids, chunk_size):
            ids_list = list(ids_chunk)
            AsyncIndicator.bulk_creation([elem[1] for elem in ids_list], 'CommCareCase', 'icds-cas', [person_config._id])
            count += chunk_size
            print("Success till doc_id: {}".format(ids_list[-1]))
            print("progress: {}/{}".format(count, total_doc_ids))

