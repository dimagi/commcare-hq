import csv

from datetime import datetime
from collections import defaultdict
from django.core.management.base import BaseCommand, CommandError

from corehq.apps.hqcase.utils import bulk_update_cases
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import CommCareCaseSQL
from custom.enikshay.case_utils import (
    get_person_case_from_occurrence,
    CASE_TYPE_DRUG_RESISTANCE,
)
from custom.enikshay.const import (
    ENROLLED_IN_PRIVATE,
)

DOMAIN = "enikshay"


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--dry_run', action='store_true')

    def handle(self, *args, **options):
        self.dry_run = options.get('dry_run')
        self.result_file = self.setup_result_file()
        self.drug_id_values = []
        self.sensitivity_values = []
        accessor = CaseAccessors(DOMAIN)
        # iterate all occurrence cases
        for occurrence_case_id in self._get_occurrence_case_ids_to_process():
            occurrence_case = accessor.get_case(occurrence_case_id)
            # Need to consider only public app cases so skip updates if enrolled in private
            if self.public_app_case(occurrence_case):
                self.reconcile_case(occurrence_case)

        print("All drug id values found %s" % self.drug_id_values)
        print("All sensitivity values found %s" % self.sensitivity_values)

    @staticmethod
    def get_result_file_headers():
        return [
            "occurrence_case_id",
            "drug_id",
            "retain_case_id",
            "retain_reason",
            "closed_case_ids"
        ]

    def setup_result_file(self):
        file_name = "drug_resistance_reconciliation_report_{timestamp}.xlsx".format(
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

    @staticmethod
    def public_app_case(occurrence_case):
        person_case = get_person_case_from_occurrence(DOMAIN, occurrence_case.get_id)
        person_case_properties = person_case.dynamic_case_properties()
        if person_case_properties.get(ENROLLED_IN_PRIVATE) == 'true':
            return False
        return True

    def reconcile_case(self, occurrence_case):
        # get all open drug resistance cases
        # group by drug_id
        # if any drug_id has more than one corresponding drug resistance case, fix them
        drug_resistance_cases = get_open_drug_resistance_cases_from_occurrence(occurrence_case.get_id)
        drug_resistance_cases_by_drug_id = defaultdict(list)
        for drug_resistance_case in drug_resistance_cases:
            drug_id = drug_resistance_case.dynamic_case_properties().get('drug_id')
            if drug_id not in self.drug_id_values:
                print("New drug_id value found, %s" % drug_id)
                self.drug_id_values.append(drug_id)
            drug_resistance_cases_by_drug_id[drug_id].append(drug_resistance_case)
        for drug_id in drug_resistance_cases_by_drug_id:
            if len(drug_resistance_cases_by_drug_id[drug_id]) > 1:
                self.reconcile_drug_resistance_cases(drug_resistance_cases, drug_id, occurrence_case.get_id)

    def reconcile_drug_resistance_cases(self, drug_resistance_cases, drug_id, occurrence_case_id):
        """
        Take cases with the same drug_id and then keep only one and close others.
        Find the one in this order
        - that has sensitivity resistant
        - that has sensitivity sensitive
        - the first ever opened case
        :param drug_resistance_cases: under an occurrence with the same drug_id
        """
        # sanity check that we got more than one case so we should be considering closing cases
        # and confirm that all have the same drug id
        if (len(drug_resistance_cases) < 2 or
            any(drug_resistance_case.dynamic_case_properties().get('drug_id') != drug_id for
                drug_resistance_case in drug_resistance_cases)):
            raise CommandError("Asked to reconcile cases when not needed for occurrence case %s"
                               % occurrence_case_id)

        drug_resistance_case_ids = set([case.get_id for case in drug_resistance_cases])
        resistant_drug_resistance_cases = []
        sensitive_drug_resistance_cases = []

        # group cases by their sensitivity
        # possible values are resistant/ sensitive/ unknown
        for drug_resistance_case in drug_resistance_cases:
            case_props = drug_resistance_case.dynamic_case_properties()
            sensitivity = case_props.get('sensitivity')
            if sensitivity == 'resistant':
                resistant_drug_resistance_cases.append(drug_resistance_case)
            elif sensitivity == 'sensitive':
                sensitive_drug_resistance_cases.append(drug_resistance_case)
            else:
                if sensitivity not in self.sensitivity_values:
                    print("New sensitivity value found, %s" % sensitivity)
        resistant_drug_resistance_cases_count = len(resistant_drug_resistance_cases)
        sensitive_drug_resistance_cases_count = len(resistant_drug_resistance_cases)

        # if there are more than one cases with sensitivity resistant, keep the one
        # opened first.
        if resistant_drug_resistance_cases_count > 1:
            retain_case_id = sorted(resistant_drug_resistance_cases, key=lambda x: x.opened_on)[0]
            cases_to_close = drug_resistance_case_ids.remove(retain_case_id)
            self.close_cases(cases_to_close, occurrence_case_id, drug_id, retain_case_id,
                             "More than one resistance drug cases, picked first opened.")
        # if there is only one case with sensitivity resistant, keep that, close rest.
        elif resistant_drug_resistance_cases_count == 1:
            retain_case_id = resistant_drug_resistance_cases[0].get_id
            cases_to_close = drug_resistance_case_ids.remove(retain_case_id)
            self.close_cases(cases_to_close, occurrence_case_id, drug_id, retain_case_id,
                             "Only one resistance drug case found.")
        # if there are more than one cases with sensitivity sensitive, keep the one
        # opened first.
        elif sensitive_drug_resistance_cases_count > 1:
            retain_case_id = sorted(sensitive_drug_resistance_cases, key=lambda x: x.opened_on)[0]
            cases_to_close = drug_resistance_case_ids.remove(retain_case_id)
            self.close_cases(cases_to_close, occurrence_case_id, drug_id, retain_case_id,
                             "More than one sensitive drug cases, picked first opened.")
        # if there is only one case with sensitivity sensitive, keep that, close rest.
        elif sensitive_drug_resistance_cases_count == 1:
            retain_case_id = sensitive_drug_resistance_cases[0].get_id
            cases_to_close = drug_resistance_case_ids.remove(retain_case_id)
            self.close_cases(cases_to_close, occurrence_case_id, drug_id, retain_case_id,
                             "Only one resistance drug case found.")
        # No case has sensitivity resistant and sensitive. Probably multiple cases with unknown status
        # keep the one opened first, close rest.
        else:
            retain_case_id = sorted(drug_resistance_cases, key=lambda x: x.opened_on)[0]
            cases_to_close = drug_resistance_case_ids.remove(retain_case_id)
            self.close_cases(cases_to_close, occurrence_case_id, drug_id, retain_case_id,
                             "Picked first opened.")

    @staticmethod
    def _get_occurrence_case_ids_to_process():
        from corehq.sql_db.util import get_db_aliases_for_partitioned_query
        dbs = get_db_aliases_for_partitioned_query()
        for db in dbs:
            case_ids = (
                CommCareCaseSQL.objects
                .using(db)
                .filter(domain=DOMAIN, type="occurrence")
                .values_list('case_id', flat=True)
            )
            num_case_ids = len(case_ids)
            print("processing %d docs from db %s" % (num_case_ids, db))
            for i, case_id in enumerate(case_ids):
                yield case_id
                if i % 1000 == 0:
                    print("processed %d / %d docs from db %s" % (i, num_case_ids, db))

    def close_cases(self, cases_to_close, occurrence_case_id, drug_id, retain_case_id, retain_reason):
        if self.dry_run:
            closing_case_ids = [case.get_id for case in cases_to_close]
            self.writerow({
                "occurrence_case_id": occurrence_case_id,
                "drug_id": drug_id,
                "retain_case_id": retain_case_id,
                "retain_reason": retain_reason,
                "closed_case_ids": closing_case_ids
            })
        else:
            updates = [(case.get_id, {'close_reason': "duplicate_reconciliation"}, True)
                       for case in cases_to_close]
            bulk_update_cases(DOMAIN, updates, self.__module__)


def get_open_drug_resistance_cases_from_occurrence(occurrence_case_id):
    case_accessor = CaseAccessors(DOMAIN)
    all_cases = case_accessor.get_reverse_indexed_cases([occurrence_case_id])
    return [case for case in all_cases
            if not case.closed and case.type == CASE_TYPE_DRUG_RESISTANCE]
