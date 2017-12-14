from __future__ import absolute_import
from __future__ import print_function
from collections import defaultdict
import csv
import datetime
from django.core.management.base import BaseCommand

from dimagi.utils.decorators.memoized import memoized

from corehq.apps.case_search.models import CLAIM_CASE_TYPE
from corehq.apps.locations.models import SQLLocation
from corehq.apps.hqcase.utils import bulk_update_cases
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.log import with_progress_bar

from custom.enikshay.case_utils import (
    CASE_TYPE_EPISODE,
    CASE_TYPE_INVESTIGATION,
    CASE_TYPE_OCCURRENCE,
    CASE_TYPE_PERSON,
    CASE_TYPE_REFERRAL,
    CASE_TYPE_SECONDARY_OWNER,
    CASE_TYPE_TEST,
    CASE_TYPE_TRAIL,
    get_all_occurrence_cases_from_person,
)
from custom.enikshay.duplicate_ids import get_cases_with_duplicate_ids, get_new_readable_id
from custom.enikshay.user_setup import compress_nikshay_id, join_chunked


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
        self.accessor = CaseAccessors(domain)
        commit = options['commit']

        filename = '{}-{}.csv'.format(self.__module__.split('.')[-1],
                                      datetime.datetime.now().strftime('%Y-%m-%d_%H.%M.%S'))
        print("Logging actions to {}".format(filename))
        with open(filename, 'w') as f:
            self.logfile = csv.DictWriter(f, self.logfile_fields, extrasaction='ignore')
            self.logfile.writeheader()

            print("Finding duplicates")
            bad_cases = get_cases_with_duplicate_ids(self.domain, CASE_TYPE_PERSON)

            print("Processing duplicate cases")
            for person_case in with_progress_bar(bad_cases):
                self.log_person_case_info(person_case)
                updates = self.get_updates(person_case)
                bulk_update_cases(self.domain, updates, self.__module__)

    @property
    @memoized
    def districts_by_id(self):
        locs = SQLLocation.objects.filter(domain=self.domain, location_type__code='dto')
        return defaultdict(lambda: '', (
            (loc.location_id, loc.loc_name) for loc in locs
        ))

    def log_person_case_info(self, person_case):
        """Pull info that we want to log but not update"""
        person = person_case.dynamic_case_properties()
        self.logfile.writerow({
            'person_case_id': person_case.case_id,
            'name': ' '.join(filter(None, [person.get('first_name'), person.get('last_name')])),
            'dto_name': self.districts_by_id(person.get('current_address_district_choice')),
            'phi_name': person.get('phi'),
            'owner_id': person_case.owner_id,
            'dob': person.get('dob'),
            'phone_number': person.get('contact_phone_number'),
        })

    def get_reverse_indexed(self, case, case_type):
        all_cases = self.accessor.get_reverse_indexed_cases([case.case_id])
        return [case for case in all_cases if case.type == case_type]

    def get_updates(self, person_case):
        """ Get updates for a person case and a bunch of its children
        https://docs.google.com/document/d/1NS5ozgk7w-2AADsrdTtjgqODkgWIEaCw6eqQ0cLg138/edit#
        """
        old_id = person_case.get_case_property('person_id')
        new_id = get_new_readable_id()  # TODO uppercase
        yield get_case_update(person_case, {
            'person_id_deprecated': old_id,
            'person_id_flat_deprecated': person_case.get_case_property('person_id_flat'),
            'person_id': new_id,
            'person_id_flat': new_id.replace('-', ''),
        })

        for person_child_case in self.accessor.get_reverse_indexed_cases([person_case.case_id]):

            # Update occurrence and claim names
            if person_child_case.type in (CASE_TYPE_OCCURRENCE, CLAIM_CASE_TYPE):
                yield get_name_update(person_child_case, old_id, new_id)

            # look at all extensions of the occurrence cases
            if person_child_case.type == CASE_TYPE_OCCURRENCE:
                for case in self.accessor.get_reverse_indexed_cases([person_child_case.case_id]):

                    # update the names of episode, secondary_owner, trail, and referral cases
                    if case.type in (CASE_TYPE_EPISODE, CASE_TYPE_SECONDARY_OWNER,
                                     CASE_TYPE_TRAIL, CASE_TYPE_REFERRAL):
                        yield get_name_update(case, old_id, new_id)

                    if case.type == CASE_TYPE_TEST:
                        yield get_case_update(case, {
                            'person_id_at_request': new_id,
                            'person_id_flat_at_request': new_id.replace('-', '')
                        })

                    if case.type == CASE_TYPE_EPISODE:
                        for investigation_case in self.accessor.get_reverse_indexed_cases([case.case_id]):
                            if investigation_case.type == CASE_TYPE_INVESTIGATION:
                                yield get_name_update(investigation_case, old_id, new_id)


def get_case_update(case, update):
    # check that this is actually an update, else return None
    if any(case.get_case_property(k) != v for k, v in update.items()):
        return (case.case_id, update, False)


def get_name_update(case, old_id, new_id):
    new_name = case.get_case_property('name').replace(old_id, new_id)
    return get_case_update(case, {'name': new_name})
