from django.core.management.base import BaseCommand, CommandError
from corehq.blobs import CODES, get_blob_db


class Command(BaseCommand):

    data_type_blob_id_map = {
        'form': 'reconcile_es_forms',
        'case': 'reconcile_es_cases',
        'missed_forms': 'es_forms_past_window',
        'missed_cases': 'es_cases_past_window',
    }

    def add_arguments(self, parser):
        parser.add_argument('data_type')
        parser.add_argument('date')

    def handle(self, data_type, date, **options):
        blob_db = get_blob_db()
        parent_id = self.data_type_blob_id_map.get(data_type)
        if parent_id is None:
            raise CommandError(f'data_type must be in {", ".join(self.data_type_blob_id_map.keys())}')
        key = f'{parent_id}_{date}'
        blob = blob_db.get(
            key=key,
            type_code=CODES.tempfile
        )
        data = blob.read().decode('utf-8')
        self.stdout.write(data)
