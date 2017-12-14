from __future__ import absolute_import
from __future__ import print_function
from collections import defaultdict
import csv
import datetime
from django.core.management.base import BaseCommand

from dimagi.utils.decorators.memoized import memoized

from corehq.apps.locations.models import SQLLocation
from corehq.apps.hqcase.utils import bulk_update_cases
from corehq.util.log import with_progress_bar

from custom.enikshay.case_utils import CASE_TYPE_PERSON
from custom.enikshay.duplicate_ids import get_cases_with_duplicate_ids


class Command(BaseCommand):
    help = """
    Finds cases with duplicate IDs and marks all but one of each ID as a duplicate
    """
    # TODO what are the headers we need?
    logfile_fields = ['name', 'dto_name', 'phi_name', 'owner_id', 'dob', 'phone_number']

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            '--commit',
            action='store_true',
            dest='commit',
            default=False,
        )

    def handle(self, domain, **options):
        self.domain = domain
        commit = options['commit']

        filename = '{}-{}.csv'.format(self.__module__.split('.')[-1],
                                      datetime.datetime.now().strftime('%Y-%m-%d_%H.%M.%S'))
        print("Logging actions to {}".format(filename))
        with open(filename, 'w') as f:
            logfile = csv.DictWriter(f, self.logfile_fields, extrasaction='ignore')
            logfile.writeheader()

            print("Finding duplicates")
            bad_cases = get_cases_with_duplicate_ids(self.domain, CASE_TYPE_PERSON)

            print("Processing duplicate cases")
            for person_case in with_progress_bar(bad_cases):
                updates = self.get_updates(person_case)
                case_info = self.get_person_case_info(person_case)
                for update in updates:
                    logfile.writerow(update)
                bulk_update_cases(self.domain, updates, self.__module__)

    @staticmethod
    def get_updates(person_case):
        pass

    @property
    @memoized
    def districts_by_id(self):
        locs = SQLLocation.objects.filter(domain=self.domain, location_type__code='dto')
        return defaultdict(lambda: '', (
            (loc.location_id, loc.loc_name) for loc in locs
        ))

    def get_person_case_info(self, person_case):
        """Pull info that we want to log but not update"""
        person = person_case.dynamic_case_properties()
        return {
            'name': ' '.join(filter(None, [person.get('first_name'), person.get('last_name')])),
            'dto_name': self.districts_by_id(person.get('current_address_district_choice')),
            'phi_name': person.get('phi'),
            'owner_id': person_case.owner_id,
            'dob': person.get('dob'),
            'phone_number': person.get('contact_phone_number'),
        }
