import csv
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from collections import defaultdict

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import CommCareCaseSQL
from custom.enikshay.case_utils import (
    CASE_TYPE_OCCURRENCE,
    CASE_TYPE_EPISODE,
    CASE_TYPE_INVESTIGATION,
)
from corehq.apps.hqcase.utils import bulk_update_cases
from custom.enikshay.const import ENROLLED_IN_PRIVATE

DOMAIN = "enikshay"
EPISODE_TYPE = "confirmed_drtb"
DATE_MODIFIED_FIELD = "modified_on"
PROPERTIES_TO_BE_COALESCED = [
    "lft_results",
    "blood_urea_results",
    "other_results",
    "tsh_results",
    "s_cr_results",
    "serum_lipase_results",
    "audiogram_results",
    "urinegravindex_results",
    "ecgqtc_results",
    "electrolyte_results",
    "upt_results",
    "cbcplatelets_results",
    "culture_date",
    "culture_lab_serial_number",
    "culture_result_value",
]


class Command(BaseCommand):
    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        self.dry_run = options.get('dry_run')
        self.result_file = self.setup_result_file()
        self.case_accessor = CaseAccessors(DOMAIN)
        self.investigation_interval_values = []
        # iterate all person cases
        for person_case_id in self._get_open_person_case_ids_to_process():
            person_case = self.case_accessor.get_case(person_case_id)
            if self.public_app_case(person_case):
                open_confirmed_drtb_episode_cases = get_open_confirmed_drtb_episode_cases(person_case_id)
                for episode_case in open_confirmed_drtb_episode_cases:
                    investigations_to_be_reconciled = self.episode_case_needs_reconciliation(episode_case)
                    if investigations_to_be_reconciled:
                        pass

    @staticmethod
    def get_result_file_headers():
        headers = [
            "episode_case_id",
            "investigation_interval",
            "investigation_case_id",
            "modified_on",
            "updates",
            "update/close"
        ]
        headers += PROPERTIES_TO_BE_COALESCED
        return headers

    def setup_result_file(self):
        file_name = "duplicate_occurrence_and_episode_reconciliation_report_{timestamp}.csv".format(
            timestamp=datetime.now().strftime("%Y-%m-%d-%H-%M-%S"),
        )
        with open(file_name, 'w') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.get_result_file_headers())
            writer.writeheader()
        return file_name

    def writerow(self, row):
        with open(self.result_file, 'a') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.get_result_file_headers())
            writer.writerow(row)

    def reconcile_investigation_cases(self, investigation_cases):
        latest_investigation_case = sorted(investigation_cases, key=lambda x: x.modified_on)[0]
        for case_property in PROPERTIES_TO_BE_COALESCED:
            all_property_values = []
            for investigation_case in investigation_cases:
                all_property_values.append(investigation_case.get_case_property(case_property))
            coalesced_value = self.get_coalesced_value_for_case_property(
                case_property, all_property_values
            )

    def close_or_update_investigation_cases(self, all_cases, retain_case_id, episode_case_id,
                                            investigation_interval, updates):
        all_case_ids = [investigation_case.case_id for investigation_case in all_cases]
        # ToDo: refetch investigation_cases in case the len of set is different from list
        # remove duplicates in case ids to remove so that we don't retain and close
        # the same case by mistake
        all_case_ids = set(all_case_ids)
        case_ids_to_close = all_case_ids.copy()
        case_ids_to_close.remove(retain_case_id)
        for investigation_case in all_cases:
            self.writerow({
                "episode_case_id": episode_case_id,
                "investigation_interval": investigation_interval,
                "investigation_case_id": investigation_case.case_id,
                "modified_on": investigation_case.get_case_property(DATE_MODIFIED_FIELD),
                "updates": case_updates,
                "update/close": ('update' if investigation_case.case_id == retain_case_id
                                 else 'closed')
            })
        if not self.dry_run:
            updates = [(case_id, {'close_reason': "duplicate_reconciliation"}, True)
                       for case_id in case_ids_to_close]
            bulk_update_cases(DOMAIN, updates, self.__module__)

    def get_coalesced_value_for_case_property(self, case_property, all_values):
        #ToDo: write logic for this
        return all_values[0]

    def episode_case_needs_reconciliation(self, episode_case):
        investigation_cases = get_investigation_cases_from_episode(episode_case)
        investigation_cases_by_interval = defaultdict(list)
        for investigation_case in investigation_cases:
            investigation_case_interval = investigation_case.get_case_property("investigation_interval")
            if investigation_case_interval not in self.investigation_interval_values:
                self.investigation_interval_values.append(investigation_case_interval)
            investigation_cases_by_interval[investigation_case_interval].append(
                investigation_case
            )
        for interval_type, investigation_cases in investigation_cases_by_interval.items():
            if len(investigation_cases) > 1:
                return investigation_cases_by_interval
        return False

    @staticmethod
    def public_app_case(person_case):
        if person_case.get_case_property(ENROLLED_IN_PRIVATE) == 'true':
            return False
        return True

    @staticmethod
    def _get_open_person_case_ids_to_process():
        from corehq.sql_db.util import get_db_aliases_for_partitioned_query
        dbs = get_db_aliases_for_partitioned_query()
        for db in dbs:
            case_ids = (
                CommCareCaseSQL.objects
                .using(db)
                .filter(domain=DOMAIN, type="person", closed=False)
                .values_list('case_id', flat=True)
            )
            num_case_ids = len(case_ids)
            print("processing %d docs from db %s" % (num_case_ids, db))
            for i, case_id in enumerate(case_ids):
                yield case_id
                if i % 1000 == 0:
                    print("processed %d / %d docs from db %s" % (i, num_case_ids, db))


def get_all_occurrence_cases_from_person(person_case_id):
    case_accessor = CaseAccessors(DOMAIN)
    all_cases = case_accessor.get_reverse_indexed_cases([person_case_id])
    return [case for case in all_cases if case.type == CASE_TYPE_OCCURRENCE]


def get_open_confirmed_drtb_episode_cases(person_case_id):
    occurrence_cases = get_all_occurrence_cases_from_person(
        person_case_id
    )
    open_confirmed_drtb_episode_cases = []
    for occurrence_case in occurrence_cases:
        case_accessor = CaseAccessors(DOMAIN)
        all_cases = case_accessor.get_reverse_indexed_cases([occurrence_case.case_id])
        open_confirmed_drtb_episode_cases += [
            case for case in all_cases
            if not case.closed
            and case.type == CASE_TYPE_EPISODE
            and case.get_case_property("episode_type") == EPISODE_TYPE
        ]
    return open_confirmed_drtb_episode_cases


def get_investigation_cases_from_episode(episode_case):
    case_accessor = CaseAccessors(DOMAIN)
    all_cases = case_accessor.get_reverse_indexed_cases([episode_case.case_id])
    return [case for case in all_cases if case.type == CASE_TYPE_INVESTIGATION]
