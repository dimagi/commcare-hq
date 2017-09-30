import csv

from datetime import datetime
from django.core.management.base import BaseCommand, CommandError

from corehq.apps.hqcase.utils import bulk_update_cases
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import CommCareCaseSQL
from custom.enikshay.case_utils import (
    CASE_TYPE_OCCURRENCE,
    CASE_TYPE_EPISODE,
    get_occurrence_case_from_episode)
from custom.enikshay.const import (
    ENROLLED_IN_PRIVATE,
)


DOMAIN = "enikshay"


class Command(BaseCommand):
    """
    1. If an open person case has multiple open occurrence cases
       we need to keep one which is relevant and close others
    2. If an open occurrence case has multiple open episode cases with
       case property is_active = "yes", we need to reconcile them
    """
    def add_arguments(self, parser):
        parser.add_argument('--dry_run', action='store_true')

    def handle(self, *args, **options):
        self.dry_run = options.get('dry_run')
        self.result_file = self.setup_result_file()
        self.case_accessor = CaseAccessors(DOMAIN)
        # iterate all person cases
        for person_case_id in self._get_open_person_case_ids_to_process():
            person_case = self.case_accessor.get_case(person_case_id)
            if self.public_app_case(person_case):
                open_occurrence_cases = get_open_occurrence_cases_from_person(person_case_id)
                if len(open_occurrence_cases) > 1:
                    # reconcile occurrence cases
                    # also reconcile episode cases under these if needed
                    self.reconcile_cases(open_occurrence_cases, person_case_id)
                else:
                    # if needed reconcile episode cases under the open occurrence case
                    self.get_open_reconciled_episode_cases_for_occurrence(open_occurrence_cases[0].get_id)

    def reconcile_cases(self, open_occurrence_cases, person_case_id):
        """
        For each occurrence, use the following priority order to identify which (single)
            has an open episode case where is_active=yes, episode_type = confirmed_drtb
                if multiple, pick first opened from relevant occurrence case
            has an open episode case where is_active=yes, episode_type = confirmed_tb
                if multiple, pick first opened from relevant occurrence case
            @date_opened (first opened occurrence case)
        """
        open_occurrence_case_ids = [case.id for case in open_occurrence_cases]
        # get all episode cases for all open occurrences
        all_episode_cases = []
        for open_occurrence_case_id in open_occurrence_case_ids:
            all_episode_cases += self.get_open_reconciled_episode_cases_for_occurrence(open_occurrence_case_id)

        active_episode_confirmed_drtb_cases = []
        active_episode_confirmed_tb_cases = []
        for episode_case in all_episode_cases:
            episode_case_properties = episode_case.dynamic_case_properties()
            if episode_case_properties.get('is_active') == 'yes':
                if episode_case_properties.get('episode_type') == 'confirmed_drtb':
                    active_episode_confirmed_drtb_cases.append(episode_case)
                elif episode_case_properties.get('episode_type') == 'confirmed_tb':
                    active_episode_confirmed_tb_cases.append(episode_case)

        active_episode_confirmed_drtb_cases_count = len(active_episode_confirmed_drtb_cases)
        active_episode_confirmed_tb_cases_count = len(active_episode_confirmed_tb_cases)

        if active_episode_confirmed_drtb_cases_count == 1:
            episode_case_id = active_episode_confirmed_drtb_cases[0].get_id
            retain_case_id = get_occurrence_case_from_episode(DOMAIN, episode_case_id).get_id
        elif active_episode_confirmed_drtb_cases_count > 1:
            relevant_occurrence_cases = []
            for active_episode_confirmed_drtb_case in active_episode_confirmed_drtb_cases:
                relevant_occurrence_cases += get_occurrence_case_from_episode(
                    DOMAIN, active_episode_confirmed_drtb_case.get_id)
            retain_case_id = sorted(relevant_occurrence_cases, key=lambda x: x.opened_on)[0].get_id
        elif active_episode_confirmed_tb_cases_count == 1:
            episode_case_id = active_episode_confirmed_tb_cases[0].get_id
            retain_case_id = get_occurrence_case_from_episode(DOMAIN, episode_case_id).get_id
        elif active_episode_confirmed_tb_cases_count > 1:
            relevant_occurrence_cases = []
            for active_episode_confirmed_tb_case in active_episode_confirmed_tb_cases:
                relevant_occurrence_cases += get_occurrence_case_from_episode(
                    DOMAIN, active_episode_confirmed_tb_case.get_id)
            retain_case_id = sorted(relevant_occurrence_cases, key=lambda x: x.opened_on)[0].get_id
        else:
            retain_case_id = sorted(open_occurrence_cases, key=lambda x: x.opened_on)[0].get_id
        self.close_cases(open_occurrence_case_ids, retain_case_id, person_case_id, "occurrence")

    def close_cases(self, all_case_ids, retain_case_id, associated_case_id, associated_case_type):
        # remove duplicates in case ids to remove so that we don't retain and close
        # the same case by mistake
        all_case_ids = set(all_case_ids)
        case_ids_to_close = all_case_ids.copy()
        case_ids_to_close.remove(retain_case_id)
        if self.dry_run:
            self.writerow({
                "case_type": associated_case_type,
                "associated_case_id": associated_case_id,
                "retain_case_id": retain_case_id,
                "closed_case_ids": case_ids_to_close
            })
        else:
            updates = [(case_id, {'close_reason': "duplicate_reconciliation"}, True)
                       for case_id in case_ids_to_close]
            bulk_update_cases(DOMAIN, updates, self.__module__)

    @staticmethod
    def public_app_case(person_case):
        person_case_properties = person_case.dynamic_case_properties()
        if person_case_properties.get(ENROLLED_IN_PRIVATE) == 'true':
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

    @staticmethod
    def get_result_file_headers():
        return [
            "case_type",
            "associated_case_id",
            "retain_case_id",
            "closed_case_ids"
        ]

    def setup_result_file(self):
        file_name = "duplicate_occurrence_and_episode_reconciliation_report_{timestamp}.xlsx".format(
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

    def reconcile_episode_cases(self, episode_cases, occurrence_case_id):
        """
        For each episode, use the following priority order to identify which case to keep (single)
            episode_type = confirmed_drtb
            episode_type = confirmed_tb
            @date_opened (first opened)
        """
        open_active_episode_ids = [case.get_id for case in episode_cases]
        confirmed_drtb_episode_cases = []
        confirmed_tb_episode_cases = []
        for episode_case in episode_cases:
            episode_case_properties = episode_case.dynamic_case_properties()
            if episode_case_properties.get('episode_type') == 'confirmed_drtb':
                confirmed_drtb_episode_cases.append(episode_case)
            elif episode_case_properties.get('episode_type') == 'confirmed_tb':
                confirmed_tb_episode_cases.append(episode_case)

        confirmed_drtb_episode_cases_count = len(confirmed_drtb_episode_cases)
        confirmed_tb_episode_cases_count = len(confirmed_tb_episode_cases)

        if confirmed_drtb_episode_cases_count == 1:
            retain_case_id = confirmed_drtb_episode_cases[0].get_id
        elif confirmed_drtb_episode_cases_count > 1:
            retain_case_id = sorted(confirmed_drtb_episode_cases, key=lambda x: x.opened_on)[0].get_id
        elif confirmed_tb_episode_cases_count == 1:
            retain_case_id = confirmed_tb_episode_cases[0].get_id
        elif confirmed_tb_episode_cases_count > 1:
            retain_case_id = sorted(confirmed_tb_episode_cases, key=lambda x: x.opened_on)[0].get_id
        else:
            retain_case_id = sorted(episode_cases, key=lambda x: x.opened_on)[0]
        self.close_cases(open_active_episode_ids, retain_case_id, occurrence_case_id, 'episode')

    def get_open_reconciled_episode_cases_for_occurrence(self, occurrence_case_id):
        def _get_open_episode_cases_for_occurrence(occurrence_case_id):
            all_cases = self.case_accessor.get_reverse_indexed_cases([occurrence_case_id])
            return [case for case in all_cases
                    if not case.closed and case.type == CASE_TYPE_EPISODE]

        def _get_open_active_episode_cases(episode_cases):
            return [open_episode_case
                    for open_episode_case in episode_cases
                    if open_episode_case.dynamic_case_properties().get('is_active') == 'yes']

        all_open_episode_cases = _get_open_episode_cases_for_occurrence(occurrence_case_id)
        open_active_episode_cases = _get_open_active_episode_cases(all_open_episode_cases)

        # if there are multiple active open episode cases, reconcile them first
        if len(open_active_episode_cases) > 1:
            self.reconcile_episode_cases(open_active_episode_cases, occurrence_case_id)

        # just confirm again that the episodes were reconciled well
        all_open_episode_cases = _get_open_episode_cases_for_occurrence(occurrence_case_id)
        open_active_episode_cases = _get_open_active_episode_cases(all_open_episode_cases)
        if len(open_active_episode_cases) > 1:
            raise CommandError("Resolved open active episode cases were not resolved for occurrence, %s" %
                               occurrence_case_id)

        return _get_open_episode_cases_for_occurrence(occurrence_case_id)


def get_open_occurrence_cases_from_person(person_case_id):
    case_accessor = CaseAccessors(DOMAIN)
    all_cases = case_accessor.get_reverse_indexed_cases([person_case_id])
    return [case for case in all_cases
            if not case.closed and case.type == CASE_TYPE_OCCURRENCE]
