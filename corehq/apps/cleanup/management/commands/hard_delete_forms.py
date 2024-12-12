from django.core.management.base import BaseCommand, CommandError
import csv
import itertools
from dimagi.utils.chunked import chunked
from corehq.form_processor.models import XFormInstance


INDEX_FORM_ID = 0
CHUNK_SIZE = 100


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('domain', help='Domain name that owns the forms to be deleted')
        parser.add_argument('filename', help='path to the CSV file')
        parser.add_argument('--resume_id', help='form ID to start at, within the CSV file')

    def handle(self, domain, filename, resume_id=None, **options):
        # expects the filename to have a CSV with a header containing a "Form ID" field
        with open(filename, mode='r', encoding='utf-8-sig') as csvfile:
            reader = csv.reader(csvfile, delimiter=',')
            self._process_rows(reader, domain, resume_id)

    def _process_rows(self, rows, domain, resume_id):
        header_row = next(rows)   # skip header line
        if header_row[INDEX_FORM_ID] != 'Form ID':
            raise CommandError(
                f'Expected Column {INDEX_FORM_ID} to be "Form ID", found "{header_row[INDEX_FORM_ID]}". Exiting'
            )

        num_deleted = 0

        if resume_id:
            print('resuming at: ', resume_id)
            rows = itertools.dropwhile(lambda row: row[INDEX_FORM_ID] != resume_id, rows)

        print('Starting form deletion')
        for chunk in chunked(rows, CHUNK_SIZE):
            form_ids = [row[INDEX_FORM_ID] for row in chunk]

            try:
                deleted_form_ids = set(XFormInstance.objects.hard_delete_forms(
                    domain, form_ids, return_ids=True))
            except Exception:
                print('failed during processing of: ', form_ids)
                raise

            for form_id in form_ids:
                if form_id in deleted_form_ids:
                    print('Deleted: ', form_id)
                else:
                    print('Not found:', form_id)

            num_deleted += len(deleted_form_ids)

        print(f'Complete -- removed {num_deleted} forms')
