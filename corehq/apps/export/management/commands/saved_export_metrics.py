from __future__ import absolute_import
from __future__ import unicode_literals

from io import BytesIO

import openpyxl
import six
from csv342 import csv

from django.core.management import BaseCommand

from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.domain.models import Domain
from corehq.apps.export.dbaccessors import get_case_export_instances
from corehq.privileges import DAILY_SAVED_EXPORT
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
            if not domain_has_privilege(domain_name, DAILY_SAVED_EXPORT):
                continue
            exports = get_case_export_instances(domain_name)
            for export in exports:
                if export.is_daily_saved_export and export.has_file():
                    attachment = export.get_payload()
                    if isinstance(attachment, six.text_type):
                        attachment = attachment.encode('utf-8')
                    attachment_io = BytesIO(attachment)
                    export_format = export.export_format
                    if export_format == 'xlsx':
                        workbook = openpyxl.load_workbook(attachment_io, read_only=True)
                        first_worksheet = workbook.worksheets[0]
                        row_count = column_count = 0
                        for row in first_worksheet.rows:
                            row_count += 1
                            column_count = max(column_count, len(row))
                    else:
                        row_count = ''
                        column_count = ''
                    yield [
                        export.get_id, domain_name, export.file_size, export_format, row_count, column_count
                    ]
