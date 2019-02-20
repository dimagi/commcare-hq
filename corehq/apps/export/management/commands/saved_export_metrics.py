from __future__ import absolute_import
from __future__ import unicode_literals

from io import BytesIO

import openpyxl
from csv342 import csv

from django.core.management import BaseCommand

from corehq.apps.domain.models import Domain
from corehq.apps.export.dbaccessors import get_form_export_instances
from corehq.util.log import with_progress_bar


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('filename')

    def handle(self, filename, **options):
        with open(filename, 'w') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Export ID', 'Project Space', 'Export Size (bytes)', 'Export Format', '# Rows', '# Columns'
            ])
            writer.writerows(self.get_output_rows(Domain.get_all_names()))

    @staticmethod
    def get_output_rows(domain_names):
        for domain_name in with_progress_bar(domain_names):
            exports = get_form_export_instances(domain_name)
            for export in exports:
                if export.blobs:
                    attachment = export.fetch_attachment('payload')
                    attachment_io = BytesIO(attachment)
                    export_format = export.export_format
                    if export.export_format == 'xlsx':
                        workbook = openpyxl.load_workbook(attachment_io, read_only=True)
                        first_worksheet = workbook.worksheets[0]
                        row_count = first_worksheet.max_row
                        column_count = first_worksheet.max_column
                    else:
                        row_count = ''
                        column_count = ''
                    yield [
                        export.get_id, domain_name, len(attachment), export_format, row_count, column_count
                    ]
