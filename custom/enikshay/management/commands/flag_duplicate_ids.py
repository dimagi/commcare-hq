from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
import csv
import datetime
from django.core.management.base import BaseCommand

from dimagi.utils.chunked import chunked

from corehq.apps.hqcase.utils import bulk_update_cases

from custom.enikshay.duplicate_ids import get_duplicated_case_stubs, add_debug_info_to_cases
from io import open


class Command(BaseCommand):
    help = """
    Finds cases with duplicate IDs and marks all but one of each ID as a duplicate
    """
    logfile_fields = ['case_id', 'readable_id', 'opened_on']
    logfile_debug_fields = ['form_name', 'username', 'device_number_in_form', 'real_device_number']

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('case_type')
        parser.add_argument(
            '--commit',
            action='store_true',
            dest='commit',
            default=False,
        )
        parser.add_argument(
            '--debug_info',
            action='store_true',
            dest='debug_info',
            default=False,
        )

    def handle(self, domain, case_type, **options):
        self.domain = domain
        self.case_type = case_type
        commit = options['commit']
        self.debug_info = options['debug_info']

        filename = '{}-{}.csv'.format(self.__module__.split('.')[-1],
                                      datetime.datetime.now().strftime('%Y-%m-%d_%H.%M.%S'))
        print("Logging actions to {}".format(filename))
        with open(filename, 'w') as f:
            if self.debug_info:
                fields = self.logfile_fields + self.logfile_debug_fields
            else:
                fields = self.logfile_fields
            logfile = csv.DictWriter(f, fields, extrasaction='ignore')
            logfile.writeheader()

            print("Finding duplicates")
            bad_cases = get_duplicated_case_stubs(self.domain, self.case_type)
            if self.debug_info:
                print("Adding debug info to cases")
                add_debug_info_to_cases(bad_cases, limit_debug_to=None)
            print("Processing duplicate cases")
            for case in bad_cases:
                logfile.writerow(case)
