from __future__ import absolute_import
from __future__ import unicode_literals

import csv342 as csv
import six
import sys
import time

from datetime import (
    datetime,
    date,
    timedelta,
)
from io import open
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

DATE_OF_REGISTRATION_PROPERTY = "date_of_registration"
PHONE_NUMBER_PROPERTY = "contact_phone_number"
HAS_MOBILE_PROPERTY = "has_mobile"
HAS_MOBILE_PROPERTY_NO_VALUE = "no"
CASE_ITERATION_COUNT = 10000
MAX_RESCUE_EXCEPTIONS_ON_UPDATE = 5
CSV_HEADERS = ['Case Id']

TEST_STATES = ['Test State', 'Test State 2', 'VL State', 'Trial State', 'Uttar Pradesh_GZB', 'AWW Test State']


class Command(BaseCommand):
    help = """
    Iterate person cases updated in last 180 days in a single partition,
    Find the ones which are
        - not deleted
        - not belonging to test locations,
        - with has_mobile case_property set to "no",
            - if the contact_phone_number is "91", set phone to blank,
            - and if it's present but is anything other than "91", note it down.
    Returns two lists of case ids, the ones updated and the ones with unexpected phone numbers
    """

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.db_alias = None
        self.log_progress = False
        self.case_ids_with_unexpected_phone_number = []
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

    def _store_case_ids_with_unexpected_phone_number(self):
        if self.case_ids_with_unexpected_phone_number:
            filename = 'unexpected_phone_numbers_with_91_part_%s_%s.csv' % (self.db_alias, datetime.utcnow())
            with open(filename, 'w+b') as output:
                writer = csv.writer(output)
                for case_id in self.case_ids_with_unexpected_phone_number:
                    writer.writerow([case_id])

    def _case_needs_to_be_updated(self, case):
        if case.deleted:
            return False
        assert case.type == CASE_TYPE
        if bool(case.owner_id) and case.owner_id in self.test_locations:
            return False
        if case.get_case_property(HAS_MOBILE_PROPERTY) == HAS_MOBILE_PROPERTY_NO_VALUE:
            phone_number = case.get_case_property(PHONE_NUMBER_PROPERTY)
            if not phone_number:
                return False
            if not phone_number == '91':
                self.case_ids_with_unexpected_phone_number.append(case.case_id)
                return False
            return True
        return False

    def _find_case_ids_with_invalid_phone_number(self):
        case_ids_with_invalid_phone_number = []

        start_date = date.today() - timedelta(days=180)
        reindex_accessor = CaseReindexAccessor(
            case_type='person', limit_db_aliases=[self.db_alias],
            start_date=start_date
        )

        filename = 'invalid_phone_numbers_with_91_part_%s_%s.csv' % (self.db_alias, datetime.utcnow())
        with open(filename, 'w+b') as output:
            cases_iterated = 0
            writer = csv.writer(output)
            writer.writerow(CSV_HEADERS)
            if self.log_progress:
                print('iterating now')
            for case in iter_all_rows(reindex_accessor):
                if self.log_progress and cases_iterated % CASE_ITERATION_COUNT == 0:
                    print("cases iterated: %s" % cases_iterated)
                cases_iterated += 1
                if self._case_needs_to_be_updated(case):
                    case_ids_with_invalid_phone_number.append(case.case_id)
                    writer.writerow([case.case_id])
        return case_ids_with_invalid_phone_number

    def _reassured_case_ids_to_update(self, chunk):
        # reconfirm the cases before updating to avoid removing updates in between
        # fetching case ids and updating
        invalid_cases = self.case_accessor.get_cases(list(chunk))
        case_ids_list = []
        for invalid_case in invalid_cases:
            if (invalid_case.get_case_property(HAS_MOBILE_PROPERTY) == HAS_MOBILE_PROPERTY_NO_VALUE and
                    invalid_case.get_case_property(PHONE_NUMBER_PROPERTY) == '91'):
                case_ids_list.append(invalid_case.case_id)
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
                    print("rescuing exception %s %s" % (exceptions_raised, six.text_type(e)))
                if exceptions_raised > MAX_RESCUE_EXCEPTIONS_ON_UPDATE:
                    six.reraise(*exc)
                else:
                    time.sleep(60)  # wait for 1 min before trying again
            else:
                break
        return exceptions_raised

    def _update_cases(self, case_ids_with_invalid_phone_number):
        exceptions_raised = 0
        with open('invalid_phone_numbers_with_91_part_%s_updated.csv' % self.db_alias, 'w+b') as output:
            writer = csv.writer(output)
            writer.writerow(['Case Id'])
            case_ids_to_update_chunk = list(chunked(case_ids_with_invalid_phone_number, 100))
            for chunk in with_progress_bar(case_ids_to_update_chunk):
                case_ids_list = self._reassured_case_ids_to_update(chunk)
                [writer.writerow([case_id]) for case_id in case_ids_list]
                exceptions_raised = self._submit_update_form(case_ids_list, exceptions_raised)

    def handle(self, db_alias, log_progress, **options):
        self.db_alias = db_alias
        self.log_progress = log_progress
        self.test_locations = find_test_locations()

        case_ids_with_invalid_phone_number = self._find_case_ids_with_invalid_phone_number()
        self._store_case_ids_with_unexpected_phone_number()
        if self.log_progress:
            print('starting update now for %s cases', len(case_ids_with_invalid_phone_number))
        self._update_cases(case_ids_with_invalid_phone_number)


def create_case_blocks(case_ids):
    case_blocks = []
    for case_id in case_ids:
        case_block = CaseBlock(case_id,
                               update={PHONE_NUMBER_PROPERTY: ''},
                               user_id=SYSTEM_USER_ID)
        case_block = ElementTree.tostring(case_block.as_xml())
        case_blocks.append(case_block)
    return case_blocks


def find_test_locations():
    test_locations = set()
    for location in SQLLocation.active_objects.filter(name__in=TEST_STATES, domain=DOMAIN):
        test_locations.update(location.get_descendants(include_self=True).values_list('location_id', flat=True))
    return test_locations
