from datetime import date
from django.core.management.base import BaseCommand
from corehq.apps.userreports.util import get_table_name
from corehq.apps.userreports.models import AsyncIndicator
from django.db import connections
from custom.icds_reports.models.aggregate import AwcLocation
from psycopg2.extensions import AsIs
from dimagi.utils.chunked import chunked


class Command(BaseCommand):
    help = "Rebuild Bihar delivery forms"
    BIHAR_STATE_ID = 'f9b47ea2ee2d8a02acddeeb491d3e175'

    def add_arguments(self, parser):
        parser.add_argument('--start_supervisor_id', required=False, dest='start_supervisor_id',
                            help='supervisor from where records are to fetch', default='')
        parser.add_argument('--ucr_name', required=True, dest='ucr_name',
                            help='name of the form UCR name', default='')
        parser.add_argument('--domain_name', required=True, dest='domain_name',
                            help='name of the form domain name', default='')

    def get_supervisor_ids(self, start_supervisor_id):
        return (AwcLocation.objects.filter(state_id=self.BIHAR_STATE_ID, aggregation_level=4,
                                           supervisor_id__gte=start_supervisor_id)
                .order_by('supervisor_id')
                .values_list('supervisor_id', flat=True))

    def handle(self, *args, **kwargs):
        ucr_name = kwargs.get('ucr_name')
        domain_name = kwargs.get('domain_name')
        table_name = get_table_name(domain_name, ucr_name)
        start_supervisor_id = kwargs.get('start_supervisor_id')
        bihar_state_id = 'f9b47ea2ee2d8a02acddeeb491d3e175'

        bihar_supervisor_ids = self.get_supervisor_ids(start_supervisor_id)
        count = 0
        chunk_size = 100
        for ids_chunk in chunked(bihar_supervisor_ids, chunk_size):
            query = """
                select distinct doc_id from "%(table_name)s"
                where state_id=%(bihar_state_id)s AND supervisor_id in %(sup_ids)s
                order by doc_id
            """
            query_params = {
                'table_name': AsIs(table_name),
                'bihar_state_id': bihar_state_id,
                'sup_ids': tuple(ids_chunk)
            }

            with connections['icds-ucr-citus'].cursor() as cursor:
                cursor.execute(query, query_params)
                doc_ids = cursor.fetchall()
                AsyncIndicator.objects.bulk_create([
                    AsyncIndicator(doc_id=doc_id[0],
                                   doc_type='XFormInstance',
                                   domain='icds-cas',
                                   indicator_config_ids=[f'static-{domain_name}-{ucr_name}']
                                   )
                    for doc_id in doc_ids
                ])
            count += chunk_size
            print("Success till doc_id: {}".format(list(ids_chunk)[-1]))
            print("progress: {}/{}".format(count, len(bihar_supervisor_ids)))
