from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand

import csv

from corehq.apps.data_analytics.models import MALTRow


class Command(BaseCommand):
    """
        Adds csv data to malt table for given files
        e.g. ./manage.py add_to_malt_table example.csv
    """
    help = 'Adds data to MALT table from given files'

    def add_arguments(self, parser):
        parser.add_argument(
            'file_paths',
            metavar='file_path',
            nargs='+',
        )

    def handle(self, file_paths, **options):
        for arg in file_paths:
            with open(arg, 'r') as file:
                rows = []
                reader = csv.reader(file)
                header_row = True
                for row in reader:
                    if header_row:
                        headers = row
                        header_row = False
                    else:
                        rows.append({headers[index]: item for index, item in enumerate(row)})
                MALTRow.objects.bulk_create(
                    [MALTRow(**malt_dict) for malt_dict in rows]
                )
