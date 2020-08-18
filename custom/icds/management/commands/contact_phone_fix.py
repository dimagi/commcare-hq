import csv
import six
import sys
import time

from datetime import datetime
from xml.etree import cElementTree as ElementTree

from django.core.management.base import BaseCommand

from corehq.apps.users.util import SYSTEM_USER_ID
from corehq.form_processor.backends.sql.dbaccessors import CaseReindexAccessor
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.log import with_progress_bar
from corehq.apps.locations.models import SQLLocation
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.backends.sql.dbaccessors import iter_all_rows

from dimagi.utils.chunked import chunked
from casexml.apps.case.mock import CaseBlock

DOMAIN = "icds-cas"
CASE_TYPE = "person"

PHONE_NUMBER_PROPERTY = "contact_phone_number"
HAS_MOBILE_PROPERTY = "has_mobile"
HAS_MOBILE_PROPERTY_VALUE = "yes"
CONTACT_PHONE_NUMBER_IS_VERIFIED = "contact_phone_number_is_verified"
CONTACT_PHONE_NUMBER_IS_VERIFIED_VALUE = 1
CASE_ITERATION_COUNT = 10000
MAX_RESCUE_EXCEPTIONS_ON_UPDATE = 5
CSV_HEADERS = ['Case Id']

TEST_STATES = []

for loc in SQLLocation.active_objects.filter(location_type__code='state', domain=DOMAIN):
    if loc.metadata.get('is_test_location') == 'test':
        TEST_STATES.append(loc.name)


class Command(BaseCommand):
    help = """
    Find the person cases which are
        - not deleted
        - not belonging to test locations,
        - with has_mobile case_property set to "yes",
            - if the contact_phone_number_is_verified is 1, 
            update the contact_phone_number property by appending 91 with phone_number,
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

    def _case_needs_to_be_updated(self, case):
        if case.deleted:
            return False
        assert case.type == CASE_TYPE
        if bool(case.owner_id) and case.owner_id in self.test_locations:
            return False
        if case.get_case_property(HAS_MOBILE_PROPERTY) == HAS_MOBILE_PROPERTY_VALUE:
            phone_number = case.get_case_property(PHONE_NUMBER_PROPERTY)
            phone_number_verified = case.get_case_property(CONTACT_PHONE_NUMBER_IS_VERIFIED)
            if len(phone_number) == 10 and phone_number_verified == CONTACT_PHONE_NUMBER_IS_VERIFIED_VALUE:
                return True
        return False

    def _find_case_ids_with_to_be_updated_phone_number(self):
        case_ids_with_to_be_updated_phone_number = []

        reindex_accessor = CaseReindexAccessor(
            domain=DOMAIN,
            case_type='person', limit_db_aliases=[self.db_alias],
        )

        filename = 'to_be_updated_phone_numbers_%s_%s.csv' % (self.db_alias, datetime.utcnow())
        with open(filename, 'w') as output:
            cases_iterated = 0
            writer = csv.writer(output)
            writer.writerow(CSV_HEADERS)
            if self.log_progress:
                self.stdout.write('iterating now')
            for case in iter_all_rows(reindex_accessor):
                if self.log_progress and cases_iterated % CASE_ITERATION_COUNT == 0:
                    self.stdout.write("cases iterated: %s" % cases_iterated)
                cases_iterated += 1
                if self._case_needs_to_be_updated(case):
                    case_ids_with_to_be_updated_phone_number.append(case.case_id)
                    writer.writerow([case.case_id])
        return case_ids_with_to_be_updated_phone_number

    def _reassured_case_ids_to_update(self, chunk):
        # reconfirm the cases before updating to avoid removing updates in between
        # fetching case ids and updating
        update_cases = self.case_accessor.get_cases(list(chunk))
        case_ids_list = []
        for update_case in update_cases:
            if (update_case.get_case_property(HAS_MOBILE_PROPERTY) == HAS_MOBILE_PROPERTY_VALUE and 
                len(update_case.get_case_property(PHONE_NUMBER_PROPERTY)) == 10 and 
                update_case.get_case_property(CONTACT_PHONE_NUMBER_IS_VERIFIED) == CONTACT_PHONE_NUMBER_IS_VERIFIED_VALUE):
                case_ids_list.append(update_case.case_id)
        return case_ids_list

    def _submit_update_form(self, case_ids_list, exceptions_raised):
        update_case_blocks = create_case_blocks(case_ids_list)
        for attempt in range(MAX_RESCUE_EXCEPTIONS_ON_UPDATE):
            try:
                if update_case_blocks:
                    submit_case_blocks(update_case_blocks, DOMAIN, user_id=SYSTEM_USER_ID)
            except Exception as e:
                exc = sys.exc_info()
                exceptions_raised += 1
                if self.log_progress:
                    self.stdout.write("rescuing exception %s %s" % (exceptions_raised, str(e)))
                if exceptions_raised > MAX_RESCUE_EXCEPTIONS_ON_UPDATE:
                    six.reraise(*exc)
                else:
                    time.sleep(60)  # wait for 1 min before trying again
            else:
                break
        return exceptions_raised

    def _update_cases(self, case_ids_with_to_be_updated_phone_number):
        exceptions_raised = 0
        with open('to_be_updated_phone_numbers_%s_updated.csv' % self.db_alias, 'w') as output:
            writer = csv.writer(output)
            writer.writerow(['Case Id'])
            case_ids_to_update_chunk = list(chunked(case_ids_with_to_be_updated_phone_number, 100))
            for chunk in with_progress_bar(case_ids_to_update_chunk):
                case_ids_list = self._reassured_case_ids_to_update(chunk)
                [writer.writerow([case_id]) for case_id in case_ids_list]
                exceptions_raised = self._submit_update_form(case_ids_list, exceptions_raised)

    def handle(self, db_alias, log_progress, **options):
        self.db_alias = db_alias
        self.log_progress = log_progress
        self.test_locations = find_test_locations()

        case_ids_with_to_be_updated_phone_number = self._find_case_ids_with_to_be_updated_phone_number()
        if self.log_progress:
            self.stdout.write('starting update now for %s cases', len(case_ids_with_to_be_updated_phone_number))
        self._update_cases(case_ids_with_to_be_updated_phone_number)


def create_case_blocks(case_ids):
    case_blocks = []
    for case_id in case_ids:
        updated_phone_number = '91' + case_id.get_case_property(PHONE_NUMBER_PROPERTY)
        case_block = CaseBlock.deprecated_init(case_id,
                               update={PHONE_NUMBER_PROPERTY: updated_phone_number},
                               user_id=SYSTEM_USER_ID)
        case_block = ElementTree.tostring(case_block.as_xml()).decode('utf-8')
        case_blocks.append(case_block)
    return case_blocks


def find_test_locations():
    test_locations = set()
    for location in SQLLocation.active_objects.filter(name__in=TEST_STATES, domain=DOMAIN):
        test_locations.update(location.get_descendants(include_self=True).values_list('location_id', flat=True))
    return test_locations
