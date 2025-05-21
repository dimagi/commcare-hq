import logging

from django.core.management.base import BaseCommand

from memoized import memoized

from dimagi.utils.chunked import chunked

from corehq.apps.es.case_search import CaseSearchES
from corehq.apps.fixtures.models import LookupTableRow
from corehq.apps.hqcase.utils import bulk_update_cases
from corehq.form_processor.models import CommCareCase
from corehq.util.log import with_progress_bar
from custom.abt.reports.fixture_utils import fixture_data_item_to_dict
from custom.nphcda.consts import (
    DOMAIN,
    FULLY_VACCINATED_CASE_PROPERTY,
    HOUSEHOLD_MEMBER_CASE_TYPE,
    VACCINE_SCHEDULE_TABLE_ID,
)

CHUNK_SIZE = 100
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Goal: Set case property fully_vaccinated where empty and household_member_type_display ='Under 5' depending
    on vaccines expected and already provided.

    Use lookup table and keep rows only with type=routine to get relevant vaccines and find what age they are
    needed.
    Calculate the number of antigens a child is eligible for by comparing the age_in_days case property to the
    eligible_from_days value in the lookup table for each relevant vaccine.
    For each antigen where age_in_days is greater than or equal to eligible_from_days, count it as eligible.

    fully_vaccinated should either have a 1 or 0,
    if the case property count_of_selected_antigens >= total count of eligible vaccines then 1, else 0
    """
    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit cases'
        )
        parser.add_argument(
            '--real-run',
            action='store_true',
            default=False,
            help='Do real updates'
        )

    def handle(self, *args, **options):
        self.real_run = options.get('real_run')
        self.limit = options.get('limit')

        if self.limit:
            logger.info(f"You have requested to limit cases to {self.limit}")

        if self.real_run:
            logger.warning("You are doing a real update, please confirm before proceeding.")
            confirmation = input("Y/N?")
            if confirmation != 'Y':
                logger.info("Aborting!")
                exit(0)
            else:
                logger.warning("Proceeding!")
        else:
            logger.info("This is a demo run so no real updates will be made.")

        self._update()

        logger.info("Completed. Bye!")

    def _update(self):
        query = self._get_es_query()
        expected_cases_to_be_iterated = query.count()

        logger.info(f"Expected cases to be iterated: {expected_cases_to_be_iterated}")

        self._update_cases(query)

    def _update_cases(self, query):
        total_count_of_cases_with_updates = 0

        doc_ids = with_progress_bar(
            query.get_ids(),
            query.count()
        )
        for chunk in chunked(doc_ids, CHUNK_SIZE, list):
            count_of_cases_with_updates = self._update_cases_chunk(chunk)
            logger.info(f"Cases with updates: {count_of_cases_with_updates}")
            total_count_of_cases_with_updates += count_of_cases_with_updates

        logger.info(f"Total cases with updates: {total_count_of_cases_with_updates}")

    def _get_es_query(self):
        search_string = ("household_member_type = 'under_5' and age_in_months < 60 and fully_vaccinated ='' "
                         "and antigens_received !=''")
        query = (
            CaseSearchES().
            domain(DOMAIN).
            case_type(HOUSEHOLD_MEMBER_CASE_TYPE).
            is_closed(False)
        )
        if self.limit:
            query = query.size(self.limit)
        return query.xpath_query(DOMAIN, search_string)

    def _update_cases_chunk(self, case_ids):
        cases = CommCareCase.objects.get_cases(case_ids)
        case_updates = []
        should_close_case = False
        for case in cases:
            _updates = self._case_property_updates_for_case(case)
            if _updates:
                if not self.real_run:
                    logger.info(f"{case.case_id}: {_updates}")
                case_updates.append((case.case_id, _updates, should_close_case))
        if self.real_run:
            try:
                xform, cases = bulk_update_cases(DOMAIN, case_updates, self.__module__)
                logger.info(xform.form_id + '\n')
            except Exception as e:
                logger.error('Update Failed!!!')
                logger.error(str(e))
                return 0
        return len(case_updates)

    def _case_property_updates_for_case(self, case):
        case_property_updates = {}
        age_in_days = case.get_case_property('age_in_days')
        # space separated antigen ids
        antigens_received = case.get_case_property('antigens_received')
        if antigens_received:
            count_of_antigens_received = len(antigens_received.split(' '))
        else:
            count_of_antigens_received = 0
        if age_in_days and count_of_antigens_received:
            if self._case_fully_vaccinated(age_in_days, count_of_antigens_received):
                case_property_updates = {FULLY_VACCINATED_CASE_PROPERTY: 1}
            else:
                case_property_updates = {FULLY_VACCINATED_CASE_PROPERTY: 0}
        return case_property_updates

    def _case_fully_vaccinated(self, age_in_days, count_of_antigens_received):
        eligible_vaccines = self._get_count_of_eligible_vaccines(age_in_days)
        return int(count_of_antigens_received) >= eligible_vaccines

    def _get_count_of_eligible_vaccines(self, age_in_days):
        age_in_days = int(age_in_days)
        return len(list(
            filter(lambda x: x > age_in_days, _get_vaccines_eligibilities_days())
        ))


@memoized
def _get_vaccines_eligibilities_days():
    return _get_vaccines_eligibilities().values()


def _get_vaccines_eligibilities():
    vaccines_eligibilities = {}
    fixture_data = list(LookupTableRow.objects.iter_rows(DOMAIN, table_id=VACCINE_SCHEDULE_TABLE_ID))

    for item_row in fixture_data:
        fixture_row = fixture_data_item_to_dict(item_row)
        if fixture_row['type'] == 'routine':
            if fixture_row['dose_unique_id'] in vaccines_eligibilities:
                raise Exception(f"Duplicates found for {fixture_row['dose_unique_id']}")
            else:
                vaccines_eligibilities[fixture_row['dose_unique_id']] = int(fixture_row['eligible_from_days'])

    return vaccines_eligibilities
