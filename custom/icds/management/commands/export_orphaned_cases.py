import csv

from django.core.management import BaseCommand

from corehq.apps.es import CaseES
from corehq.apps.es import filters

from dimagi.utils.chunked import chunked

from corehq.util.log import with_progress_bar

CHILD_PROPERTIES = ['case_id', 'owner_id', 'opened_on', 'server_modified_on',
                    'name', 'indices', 'aadhar_number', 'dob', 'died']


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'hh_file',
            help="File path for household case output file",
        )
        parser.add_argument(
            'child_file',
            help="File path child case output file",
        )

    def handle(self, hh_file, child_file, **options):
        hh_cases = self._get_closed_hh_cases()
        with open(hh_file, 'w') as hh_csv, open(child_file, 'w') as child_csv:
            hh_writer = csv.writer(hh_csv)
            child_writer = csv.writer(child_csv)
            for cases in chunked(with_progress_bar(hh_cases, hh_cases.count), 500):
                household_ids = []
                for hh in cases:
                    hh_writer.writerow([hh['case_id'], hh['date_closed']])
                    household_ids.append(hh['case_id'])
                child_cases = self._get_child_cases(household_ids)
                for child in child_cases.hits:
                    row = [child.get(prop, '') for prop in CHILD_PROPERTIES]
                    child_writer.writerow(row)

    def _get_closed_hh_cases(self):
        query = (CaseES()
                 .is_closed()
                 .domain('icds-cas')
                 .case_type('household')
                 .source(['case_id', 'date_closed'])
                 )
        return query.scroll()

    def _get_child_cases(self, household_ids):
        query = (CaseES()
                 .domain('icds-cas')
                 .case_type('person')
                 .source(CHILD_PROPERTIES)
                 .filter(
                    filters.nested('indices',
                                   filters.AND(
                                       filters.term("indices.referenced_id", household_ids),
                                       filters.term("indices.identifier", 'parent'))
                                   )
                    )
                )
        return query.run()
