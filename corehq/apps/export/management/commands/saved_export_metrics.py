from __future__ import absolute_import
from __future__ import unicode_literals

from io import BytesIO

import openpyxl
import six
from couchdbkit import ResourceNotFound
from csv342 import csv

from django.core.management import BaseCommand

from corehq.apps.domain.models import Domain
from corehq.apps.export.dbaccessors import get_form_export_instances
from corehq.util.log import with_progress_bar


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('filename')
        parser.add_argument('domains', nargs='*')

    def handle(self, filename, domains, **options):
        domain_names = domains or Domain.get_all_names()
        with open(filename, 'w') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Export ID', 'Project Space', 'Export Size (bytes)', 'Export Format', '# Rows', '# Columns'
            ])
            writer.writerows(self.get_output_rows(domain_names))

    @staticmethod
    def get_output_rows(domain_names):
        for domain_name in with_progress_bar(domain_names):
            exports = get_form_export_instances(domain_name)
            for export in exports:
                print(export.get_id)
                if export.is_daily_saved_export and export.has_file():
                    attachment = export.get_payload()
                    if isinstance(attachment, six.text_type):
                        attachment = attachment.encode('utf-8')
                    attachment_io = BytesIO(attachment)
                    export_format = export.export_format
                    if export_format == 'xlsx':
                        print('xlsx: %s' % export.get_id)
                        workbook = openpyxl.load_workbook(attachment_io, read_only=True)
                        first_worksheet = workbook.worksheets[0]
                        row_count = first_worksheet.max_row
                        column_count = first_worksheet.max_column
                    else:
                        print('skipping: %s' % export.get_id)
                        row_count = ''
                        column_count = ''
                    x = [
                        export.get_id, domain_name, export.file_size, export_format, row_count, column_count
                    ]
                    print(x)
                    yield x
