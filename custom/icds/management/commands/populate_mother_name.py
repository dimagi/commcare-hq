import csv
import six
import sys
import time

from datetime import (
    datetime,
    date,
    timedelta,
)
from xml.etree import cElementTree as ElementTree

from django.core.management.base import BaseCommand

from corehq.apps.users.util import SYSTEM_USER_ID
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL, CaseReindexAccessor
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.apps.locations.models import SQLLocation
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.backends.sql.dbaccessors import iter_all_rows

from casexml.apps.case.mock import CaseBlock

DOMAIN = "icds-cas"
CASE_TYPE = "person"
CUT_OFF_AGE_IN_YEARS = 6
date_today = date.today()
CUT_OFF_DOB = str(date_today.replace(year=date_today.year - CUT_OFF_AGE_IN_YEARS))

DOB_PROPERTY = "dob"
MOTHER_NAME_PROPERTY = "mother_name"
MOTHER_INDEX_IDENTIFIER = "mother"

CASE_ITERATION_COUNT = 10000
MAX_RESCUE_EXCEPTIONS_ON_UPDATE = 5

CSV_HEADERS = ['Case ID', 'Mother Case ID', 'Mother Name']


class Command(BaseCommand):
    help = """
    Iterate person cases updated in last 100 days (3 months with buffer) in a single partition,
    Find the ones which are
        - not deleted
        - not belonging to test locations,
        - with age less than 6 years using dob case property,
            - if there is related mother case, populate mother_name case property with it's name
    Returns two lists of case ids, the ones updated and the ones that could not be updated
    """

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.db_alias = None
        self.log_progress = False
        self.test_locations = None
        self.case_accessor = CaseAccessors(DOMAIN)

    def add_arguments(self, parser):
        parser.add_argument('db_alias')
        parser.add_argument(
            '--log',
            action='store_true',
            dest='log_progress',
            default=False,
            help="log progress"
        )

    def handle(self, db_alias, log_progress, **options):
        self.db_alias = db_alias
        self.log_progress = log_progress
        self.test_locations = find_test_awc_locations()

        filename = self._find_case_ids_without_mother_name()
        if self.log_progress:
            print('starting update now for cases')
        self._update_cases(filename)

    def _find_case_ids_without_mother_name(self):
        start_date = date.today() - timedelta(days=100)
        reindex_accessor = CaseReindexAccessor(
            domain=DOMAIN,
            case_type=CASE_TYPE, limit_db_aliases=[self.db_alias],
            start_date=start_date
        )

        filename = 'cases_without_mother_name_part_%s_%s.csv' % (self.db_alias, datetime.utcnow())
        cases_with_no_mother_name_filename = 'cases_with_no_mother_name_part_%s_%s.csv' % (
            self.db_alias, datetime.utcnow())
        with open(filename, 'w') as output:
            with open(cases_with_no_mother_name_filename, 'w') as no_mother_name_file:
                cases_iterated = 0
                writer = csv.writer(output)
                writer.writerow(CSV_HEADERS)
                no_mother_name_writer = csv.writer(no_mother_name_file)
                no_mother_name_writer.writerow(['Case ID'])
                if self.log_progress:
                    print('iterating now')
                for case in iter_all_rows(reindex_accessor):
                    if self.log_progress and cases_iterated % CASE_ITERATION_COUNT == 0:
                        print("cases iterated: %s" % cases_iterated)
                    cases_iterated += 1
                    if self._case_needs_to_be_updated(case):
                        mother_case_id, mother_name = self._find_mother_case_id_and_name(case)
                        if mother_case_id and mother_name:
                            writer.writerow([case.case_id, mother_case_id, mother_name])
                        else:
                            no_mother_name_writer.writerow([case.case_id])
        return filename

    def _find_mother_case_id_and_name(self, case):
        mother_case_ids = [i.referenced_id for i in CaseAccessorSQL.get_indices(DOMAIN, case.case_id)
                           if i.identifier == MOTHER_INDEX_IDENTIFIER]
        if len(mother_case_ids) == 1:
            try:
                mother_case = self.case_accessor.get_case(mother_case_ids[0])
            except CaseNotFound:
                pass
            else:
                return mother_case.case_id, mother_case.name
        return None, None

    def _case_needs_to_be_updated(self, case):
        if case.deleted:
            return False
        assert case.type == CASE_TYPE
        if bool(case.owner_id) and case.owner_id in self.test_locations:
            return False
        dob = case.get_case_property(DOB_PROPERTY)
        if dob and dob > CUT_OFF_DOB and not case.get_case_property(MOTHER_NAME_PROPERTY):
            return True
        return False

    def _update_cases(self, filename):
        exceptions_raised = 0
        updates = {}  # case id: mother name
        counter = 0
        with open(filename, 'r') as _input:
            reader = csv.DictReader(_input)
            with open('cases_without_mother_name_part_%s_updated.csv' % self.db_alias, 'w') as output:
                writer = csv.writer(output)
                writer.writerow(['Case ID', 'Mother Name'])
                for row in reader:
                    updates[row['Case ID']] = row['Mother Name']
                    counter += 1
                    if counter > 0 and counter % 100 == 0:
                        case_ids = self._reassured_case_ids_to_update(list(updates.keys()))
                        skip_ids = updates.keys() - case_ids
                        for case_id in skip_ids:
                            updates.pop(case_id)
                        for case_id, mother_name in updates.items():
                            writer.writerow([case_id, mother_name])
                        exceptions_raised = self._submit_update_form(updates, exceptions_raised)
                        if self.log_progress:
                            print("cases updated: %s" % counter)
                        updates = {}
                        counter = 0
                # update the pending batch
                for case_id, mother_name in updates.items():
                    writer.writerow([case_id, mother_name])
                exceptions_raised = self._submit_update_form(updates, exceptions_raised)

    def _submit_update_form(self, updates, exceptions_raised):
        update_case_blocks = self.create_case_blocks(updates)
        if not update_case_blocks:
            return exceptions_raised
        for attempt in range(MAX_RESCUE_EXCEPTIONS_ON_UPDATE):
            try:
                submit_case_blocks(update_case_blocks, DOMAIN, user_id=SYSTEM_USER_ID)
            except Exception as e:
                exc = sys.exc_info()
                exceptions_raised += 1
                if self.log_progress:
                    print("rescuing exception %s %s" % (exceptions_raised, str(e)))
                if exceptions_raised > MAX_RESCUE_EXCEPTIONS_ON_UPDATE:
                    six.reraise(*exc)
                else:
                    time.sleep(60)  # wait for 1 min before trying again
            else:
                break
        return exceptions_raised

    def create_case_blocks(self, updates):
        case_blocks = []
        for case_id, mother_name in updates.items():
            case_block = CaseBlock.deprecated_init(case_id,
                                   update={MOTHER_NAME_PROPERTY: mother_name},
                                   user_id=SYSTEM_USER_ID)
            case_block = ElementTree.tostring(case_block.as_xml()).decode('utf-8')
            case_blocks.append(case_block)
        return case_blocks

    def _reassured_case_ids_to_update(self, case_ids):
        # reconfirm the cases before updating to avoid removing updates in between
        # fetching case ids and updating
        invalid_cases = self.case_accessor.get_cases(case_ids)
        case_ids_list = set()
        for invalid_case in invalid_cases:
            if self._case_needs_to_be_updated(invalid_case):
                case_ids_list.add(invalid_case.case_id)
        return case_ids_list


def find_test_awc_locations():
    test_locations = set()
    for location in SQLLocation.active_objects.filter(location_type__code='state', domain=DOMAIN):
        if location.metadata.get('is_test_location') == 'test':
            test_locations.update(
                location.get_descendants(include_self=True).
                filter(location_type__code='awc').values_list('location_id', flat=True)
            )
    return test_locations
