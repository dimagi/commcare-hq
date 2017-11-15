"""
A utility that supports two commands:
    - get_row
    - get_outcome

Example usage:

    > ./manage.py drtb_import_history get_row 3c005532d11e463680b3f9124ea5b5a8 drtb-import-1340987.csv
    row: 732

    > ./manage.py drtb_import_history get_row some-bad-id drtb-import-1340987.csv
    case not found

    > ./manage.py drtb_import_history get_outcome 145 drtb-import-1340987.csv
    3c005532d11e463680b3f9124ea5b5a8
    9124ea5b5a83c005532d11e463680b3f
    463680b3f9124ea5b5a83c005532d11e
    1e46363c005532d180b3f9124ea5b5a8

    > ./manage.py drtb_import_history get_outcome 23 drtb-import-1340987.csv
    {some stack trace}

"""
from __future__ import absolute_import
from __future__ import print_function
import csv

from django.core.management import BaseCommand


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'command',
            help="get_row or get_outcome"
        )
        parser.add_argument(
            'argument',
            help="a case id or row number"
        )
        parser.add_argument(
            'csv_path',
            help="path to an drtb import log csv"
        )

    def handle(self, command, argument, csv_path, **options):
        assert command in ("get_row", "get_outcome")
        output = None

        with open(csv_path, "r") as f:
            if command == "get_row":
                output = self.handle_get_row(argument, f)
            elif command == "get_outcome":
                output = self.handle_get_outcome(argument, f)
        if output:
            print(output)

    @staticmethod
    def handle_get_row(case_id, file_):
        reader = csv.DictReader(file_)
        for row in reader:
            case_ids = row.get('case_ids', "").split(",")
            if case_id in case_ids:
                return "row: {}\n".format(row["row"])
        return "case not found\n"

    @staticmethod
    def handle_get_outcome(row_num, file_):
        output = ""
        reader = csv.DictReader(file_)
        for row in reader:
            if row_num == row['row']:
                if row['case_ids']:
                    case_ids = row['case_ids'].split(",")
                    for case_id in case_ids:
                        output += case_id + "\n"
                elif row['exception']:
                    output += row['exception'] + "\n"
                else:
                    output += "row present, but no case_ids or exception for row\n"
                return output
        output += "row not found\n"
        return output
