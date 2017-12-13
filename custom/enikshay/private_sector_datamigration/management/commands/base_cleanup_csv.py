from __future__ import absolute_import
from __future__ import print_function
import csv

from django.core.management import BaseCommand


class BaseCleanupCSVCommand(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('old_filename')
        parser.add_argument('new_filename')

    def handle(self, old_filename, new_filename, **options):
        rows = self.get_rows_from_csv_file(old_filename)
        header = rows[0]
        body = rows[1:]
        cleaned_rows = self.clean_rows(header, body)
        self.assert_rectangular_matrix(cleaned_rows)
        self.write_to_csv(cleaned_rows, new_filename)
        print('outputted to %s' % new_filename)

    @staticmethod
    def get_rows_from_csv_file(filename):
        with open(filename, 'rU') as csvfile:
            csvreader = csv.reader(csvfile)
            return list(csvreader)

    @staticmethod
    def assert_rectangular_matrix(matrix):
        assert len({len(row) for row in matrix}) == 1

    @staticmethod
    def write_to_csv(rows, filename):
        with open(filename, 'wb') as csvfile:
            csvwriter = csv.writer(csvfile)
            for row in rows:
                csvwriter.writerow(row)

    @staticmethod
    def clean_rows(header, body):
        raise NotImplementedError
