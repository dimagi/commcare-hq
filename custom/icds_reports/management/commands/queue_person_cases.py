
from django.core.management.base import BaseCommand
from corehq.apps.userreports.tasks import _get_config_by_id
from corehq.apps.userreports.util import get_table_name
from corehq.apps.userreports.models import AsyncIndicator
from django.db import connections

from dimagi.utils.chunked import chunked


class Command(BaseCommand):
    help = "Rebuild Bihar person cases "

    def handle(self):
        person_config = _get_config_by_id('static-icds-cas-static-person_cases_v3')
        table_name = get_table_name('icds-cas', 'static-person_cases_v3')
        query = """select doc_id from "{}" where state_id='f9b47ea2ee2d8a02acddeeb491d3e175' order by doc_id""".format(table_name)

        with connections['icds-ucr-citus'].cursor() as cursor:
            cursor.execute(query)
            doc_ids = cursor.fetchall()

        total_doc_ids = len(doc_ids)
        count = 0
        for ids_chunk in chunked(doc_ids, 10000):
            ids_list = [item[0] for item in ids_chunk]
            AsyncIndicator.bulk_creation(ids_list, 'case', 'icds-cas', [person_config._id])
            count += 10000
            print("Success till doc_id: {}".format(ids_list[-1]))
            print("progress: {}/{}".format(count, total_doc_ids ))
