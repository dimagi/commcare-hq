import csv
import itertools

from dimagi.utils.chunked import chunked
from django.core.management.base import BaseCommand, CommandError

from corehq.form_processor.models import XFormInstance

INDEX_FORM_ID = 0
CHUNK_SIZE = 100


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('domain', help='Domain name that owns the forms to be deleted')
        parser.add_argument('filename', help='path to the CSV file')
        parser.add_argument('--resume_id', help='form ID to start at, within the CSV file')

    def handle(self, domain, filename, resume_id=None, permanent=False, **options):
        # expects the filename to have a CSV with a header containing a "Form ID" field
        with open(filename, mode='r', encoding='utf-8-sig') as csvfile:
            reader = csv.reader(csvfile, delimiter=',')
            self._process_rows(reader, domain, resume_id, permanent)

    def _process_rows(self, rows, domain, resume_id, permanent):
        header_row = next(rows)  # skip header line
        if header_row[INDEX_FORM_ID] != 'Form ID':
            raise CommandError(
                f'Expected Column {INDEX_FORM_ID} to be "Form ID", found "{header_row[INDEX_FORM_ID]}". Exiting'
            )

        if resume_id:
            print('resuming at: ', resume_id)
            rows = itertools.dropwhile(lambda row: row[INDEX_FORM_ID] != resume_id, rows)

        self.delete_forms(domain, rows, permanent)

    def delete_forms(self, domain, rows, permanent):
        print('Starting form deletion')
        num_deleted = 0
        for chunk in chunked(rows, CHUNK_SIZE):
            form_ids = [row[INDEX_FORM_ID] for row in chunk]
            try:
                num_deleted += self.soft_delete_forms(domain, form_ids)
            except Exception:
                print('Failed whilte attempting to delete:', form_ids)
                raise
        print(f'Completed soft deletion of {num_deleted} forms')

    def soft_delete_forms(self, domain, form_ids):
        print("Soft deleted chunk:", form_ids)
        return XFormInstance.objects.soft_delete_forms(domain, form_ids, deletion_id='delete_forms_cmd')
