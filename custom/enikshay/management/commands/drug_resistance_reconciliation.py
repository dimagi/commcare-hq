from collections import defaultdict

from django.core.management.base import CommandError

from corehq.apps.hqcase.utils import bulk_update_cases
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import CommCareCaseSQL
from custom.enikshay.case_utils import (
    get_person_case_from_occurrence,
    CASE_TYPE_DRUG_RESISTANCE,
)
from custom.enikshay.management.commands.base_model_reconciliation import (
    BaseModelReconciliationCommand,
    DOMAIN,
    get_all_occurrence_case_ids_from_person,
)
from custom.enikshay.exceptions import ENikshayCaseNotFound
from custom.enikshay.const import (
    DRUG_RESISTANCE_SENSITIVITY,
    DRUG_RESISTANCE_SENSITIVITY_RESISTANT,
    DRUG_RESISTANCE_SENSITIVITY_SENSITIVE,
)


class Command(BaseModelReconciliationCommand):
    email_subject = "Drug Resistance Reconciliation Report"
    result_file_name_prefix = "drug_resistance_reconciliation_report"
    result_file_headers = [
        "occurrence_case_id",
        "person_case_id",
        "drug_id",
        "retain_case_id",
        "retain_reason",
        "closed_case_ids",
        "closed_extension_case_ids"
    ]

    def handle(self, *args, **options):
        self.commit = options.get('commit')
        self.log_progress = options.get('log_progress')
        self.recipient = (options.get('recipient') or 'mkangia@dimagi.com')
        self.recipient = list(self.recipient) if not isinstance(self.recipient, basestring) else [self.recipient]
        self.result_file_name = self.setup_result_file()
        self.drug_id_values = []
        self.sensitivity_values = []
        self.case_accessor = CaseAccessors(DOMAIN)
        self.person_case_ids = options.get('person_case_ids')
        # iterate all occurrence cases
        for occurrence_case_id in self._get_open_occurrence_case_ids_to_process():
            # Need to consider only public app cases so skip updates if enrolled in private
            if self.public_app_case(occurrence_case_id):
                self.reconcile_case(occurrence_case_id)

        if self.log_progress:
            print("All drug id values found %s" % self.drug_id_values)
            print("All sensitivity values found %s" % self.sensitivity_values)

        self.email_report()

    def public_app_case(self, occurrence_case_id):
        try:
            person_case = get_person_case_from_occurrence(DOMAIN, occurrence_case_id)
        except ENikshayCaseNotFound:
            return False
        self.person_case_id = person_case.case_id
        return super(Command, self).public_app_case(person_case)

    def reconcile_case(self, occurrence_case_id):
        # get all open drug resistance cases
        # group by drug_id
        # if any drug_id has more than one corresponding drug resistance case, fix them
        drug_resistance_cases = get_open_drug_resistance_cases_from_occurrence(occurrence_case_id)
        drug_resistance_cases_by_drug_id = defaultdict(list)
        for drug_resistance_case in drug_resistance_cases:
            drug_id = drug_resistance_case.get_case_property('drug_id')
            if drug_id not in self.drug_id_values:
                if self.log_progress:
                    print("New drug_id value found, %s" % drug_id)
                self.drug_id_values.append(drug_id)
            drug_resistance_cases_by_drug_id[drug_id].append(drug_resistance_case)
        for drug_id, drug_resistance_cases_for_drug in drug_resistance_cases_by_drug_id.items():
            if len(drug_resistance_cases_for_drug) > 1:
                self.reconcile_drug_resistance_cases(drug_resistance_cases_for_drug, drug_id, occurrence_case_id)

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
            any(drug_resistance_case.get_case_property('drug_id') != drug_id
                for drug_resistance_case in drug_resistance_cases)):
            raise CommandError("Asked to reconcile cases when not needed for occurrence case %s"
                               % occurrence_case_id)

        resistant_drug_resistance_cases = []
        sensitive_drug_resistance_cases = []

        # group cases by their sensitivity
        # possible values are resistant/ sensitive/ unknown
        for drug_resistance_case in drug_resistance_cases:
            sensitivity = drug_resistance_case.get_case_property(DRUG_RESISTANCE_SENSITIVITY)
            if sensitivity == DRUG_RESISTANCE_SENSITIVITY_RESISTANT:
                resistant_drug_resistance_cases.append(drug_resistance_case)
            elif sensitivity == DRUG_RESISTANCE_SENSITIVITY_SENSITIVE:
                sensitive_drug_resistance_cases.append(drug_resistance_case)
            else:
                if sensitivity not in self.sensitivity_values:
                    self.sensitivity_values.append(sensitivity)
                    print("New sensitivity value found, %s" % sensitivity)
        resistant_drug_resistance_cases_count = len(resistant_drug_resistance_cases)
        sensitive_drug_resistance_cases_count = len(sensitive_drug_resistance_cases)

        # if there is more than one case with sensitivity resistant, keep the one
        # opened first.
        if resistant_drug_resistance_cases_count > 1:
            retain_case = self.get_first_opened_case(resistant_drug_resistance_cases)
            self.close_cases(drug_resistance_cases, occurrence_case_id, drug_id, retain_case,
                             "More than one resistance drug cases, picked first opened.")
        # if there is only one case with sensitivity resistant, keep that, close rest.
        elif resistant_drug_resistance_cases_count == 1:
            retain_case = resistant_drug_resistance_cases[0]
            self.close_cases(drug_resistance_cases, occurrence_case_id, drug_id, retain_case,
                             "Only one resistance drug case found.")
        # if there is more than one case with sensitivity sensitive, keep the one
        # opened first.
        elif sensitive_drug_resistance_cases_count > 1:
            retain_case = self.get_first_opened_case(sensitive_drug_resistance_cases)
            self.close_cases(drug_resistance_cases, occurrence_case_id, drug_id, retain_case,
                             "More than one sensitive drug cases, picked first opened.")
        # if there is only one case with sensitivity sensitive, keep that, close rest.
        elif sensitive_drug_resistance_cases_count == 1:
            retain_case = sensitive_drug_resistance_cases[0]
            self.close_cases(drug_resistance_cases, occurrence_case_id, drug_id, retain_case,
                             "Only one sensitive drug case found.")
        # No case has sensitivity resistant and sensitive. Probably multiple cases with unknown status
        # keep the one opened first, close rest.
        else:
            retain_case = self.get_first_opened_case(drug_resistance_cases)
            self.close_cases(drug_resistance_cases, occurrence_case_id, drug_id, retain_case,
                             "Picked first opened.")

    def _get_open_occurrence_case_ids_to_process(self):
        if self.person_case_ids:
            num_case_ids = len(self.person_case_ids)
            for i, case_id in enumerate(self.person_case_ids):
                occurrence_case_ids = get_all_occurrence_case_ids_from_person(case_id)
                for occurrence_case_id in occurrence_case_ids:
                    yield occurrence_case_id
                if i % 1000 == 0 and self.log_progress:
                    print("processed %d / %d docs" % (i, num_case_ids))
        else:
            from corehq.sql_db.util import get_db_aliases_for_partitioned_query
            dbs = get_db_aliases_for_partitioned_query()
            for db in dbs:
                case_ids = (
                    CommCareCaseSQL.objects
                    .using(db)
                    .filter(domain=DOMAIN, type="occurrence", closed=False)
                    .values_list('case_id', flat=True)
                )
                num_case_ids = len(case_ids)
                if self.log_progress:
                    print("processing %d docs from db %s" % (num_case_ids, db))
                for i, case_id in enumerate(case_ids):
                    yield case_id
                    if i % 1000 == 0 and self.log_progress:
                        print("processed %d / %d docs from db %s" % (i, num_case_ids, db))

    def close_cases(self, all_cases, occurrence_case_id, drug_id, retain_case, retain_reason):
        # remove duplicates in case ids to remove so that we dont retain and close
        # the same case by mistake
        all_case_ids = {case.case_id for case in all_cases}
        retain_case_id = retain_case.case_id
        case_ids_to_close = all_case_ids.copy()
        case_ids_to_close.remove(retain_case_id)

        case_accessor = CaseAccessors(DOMAIN)
        closing_extension_case_ids = case_accessor.get_extension_case_ids(case_ids_to_close)

        self.writerow({
            "occurrence_case_id": occurrence_case_id,
            "person_case_id": self.person_case_id,
            "drug_id": drug_id,
            "retain_case_id": retain_case_id,
            "retain_reason": retain_reason,
            "closed_case_ids": ','.join(map(str, case_ids_to_close)),
            "closed_extension_case_ids": ','.join(map(str, closing_extension_case_ids))
        })
        if self.commit:
            updates = [(case_id, {'close_reason': "duplicate_reconciliation"}, True)
                       for case_id in case_ids_to_close]
            bulk_update_cases(DOMAIN, updates, self.__module__)


def get_open_drug_resistance_cases_from_occurrence(occurrence_case_id):
    case_accessor = CaseAccessors(DOMAIN)
    all_cases = case_accessor.get_reverse_indexed_cases([occurrence_case_id])
    return [case for case in all_cases
            if not case.closed and case.type == CASE_TYPE_DRUG_RESISTANCE]
