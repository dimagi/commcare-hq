from datetime import date
from django.core.management.base import BaseCommand
from corehq.apps.userreports.tasks import _get_config_by_id
from corehq.apps.userreports.util import get_table_name
from corehq.apps.userreports.models import AsyncIndicator
from django.db import connections

from dimagi.utils.chunked import chunked


class Command(BaseCommand):
    help = "Rebuild Bihar delivery forms"

    def handle(self, *args, **kwargs):
        delivery_config = _get_config_by_id('static-icds-cas-static-child_delivery_forms')
        table_name = get_table_name('icds-cas', 'static-child_delivery_forms')
        # sort by supervisor_id and doc_id to improve the performance, sorting is needed to resume the queueing
        # if it fails in between.
        query = """
            select supervisor_id, doc_id from "{}"
            where state_id='f9b47ea2ee2d8a02acddeeb491d3e175'
            order by supervisor_id, doc_id
        """.format(table_name)

        with connections['icds-ucr-citus'].cursor() as cursor:
            cursor.execute(query)
            doc_ids = cursor.fetchall()

        total_doc_ids = len(doc_ids)
        count = 0
        chunk_size = 10000
        for ids_chunk in chunked(doc_ids, chunk_size):
            ids_list = [item for item in ids_chunk]
            AsyncIndicator.objects.bulk_create([
                AsyncIndicator(doc_id=elem[1],
                               doc_type='XFormInstance',
                               domain='icds-cas',
                               indicator_config_ids=[delivery_config._id],
                               date_created=date(2019, 1, 1)   # To prioritise in the queue
                               )
                for elem in ids_list
            ])
            count += chunk_size
            print("Success till doc_id: {}".format(ids_list[-1]))
            print("progress: {}/{}".format(count, total_doc_ids))
