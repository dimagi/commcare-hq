from django.core.management.base import BaseCommand, CommandError
from corehq.blobs import CODES, get_blob_db


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('data_type')
        parser.add_argument('date')

    def handle(self, data_type, date, **options):
        blob_db = get_blob_db()
        if data_type == 'form':
            parent_id = 'reconcile_es_forms'
        elif data_type == 'case':
            parent_id = 'reconcile_es_cases'
        else:
            raise CommandError('data_type must be either form or case')
        key = f'{parent_id}_{date}'
        blob = blob_db.get(
            key=key,
            type_code=CODES.tempfile
        )
        data = blob.read().decode('utf-8')
        self.stdout.write(data)

