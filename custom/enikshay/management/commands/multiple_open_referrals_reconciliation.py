from __future__ import absolute_import, print_function
from corehq.apps.hqcase.utils import bulk_update_cases
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import CommCareCaseSQL
from custom.enikshay.case_utils import (
    get_person_case_from_occurrence,
    CASE_TYPE_REFERRAL,
)
from custom.enikshay.management.commands.base_model_reconciliation import (
    BaseModelReconciliationCommand,
    DOMAIN,
    get_all_occurrence_case_ids_from_person,
)
from custom.enikshay.exceptions import ENikshayCaseNotFound


class Command(BaseModelReconciliationCommand):
    email_subject = "Multiple Open Referrals Reconciliation Report"
    result_file_name_prefix = "multiple_open_referrals_reconciliation_report"
    result_file_headers = [
        "occurrence_case_id",
        "retain_case_id",
        "closed_case_ids",
        "closed_extension_case_ids",
        "notes",
        "person_case_version",
        "person_case_dataset",
    ]

    def handle(self, *args, **options):
        # self.commit = options.get('commit')
        self.commit = False
        self.log_progress = options.get('log_progress')
        self.recipient = (options.get('recipient') or 'mkangia@dimagi.com')
        self.recipient = list(self.recipient) if not isinstance(self.recipient, basestring) else [self.recipient]
        self.result_file_name = self.setup_result_file()
        self.person_case_ids = options.get('person_case_ids')
        # iterate all occurrence cases
        for occurrence_case_id in self._get_open_occurrence_case_ids_to_process():
            if self.public_app_case(occurrence_case_id):
                referral_cases = get_open_referral_cases_from_occurrence(occurrence_case_id)
                if len(referral_cases) > 1:
                    self.reconcile_cases(referral_cases, occurrence_case_id)
        self.email_report()

    def reconcile_cases(self, referral_cases, occurrence_case_id):
        retain_case = self.get_case_to_be_retained(referral_cases, occurrence_case_id)
        self.close_cases(referral_cases, occurrence_case_id, retain_case)

    def get_case_to_be_retained(self, referral_cases, occurrence_case_id):
        """
        Use the following priority order to identify which case (single) to keep:
        Referral.referral_reason = enrolment if person.@owner_id = '-' OR person.@owner_id = ''
        Referral.referral_reason != enrollment if person.@owner_id != '-' AND person.@owner_id != ''
        @date_opened (earliest)
        """
        relevant_cases = []

        for referral_case in referral_cases:
            if self.person_case.owner_id in ['-', '']:
                if referral_case.get_case_property('referral_reason') == 'enrolment':
                    relevant_cases.append(referral_case)

        if not relevant_cases:
            for referral_case in referral_cases:
                if self.person_case.owner_id not in ['-', '']:
                    if referral_case.get_case_property('referral_reason') != 'enrollment':
                        relevant_cases.append(referral_case)

        if relevant_cases:
            if len(relevant_cases) > 1:
                return self.get_first_opened_case(relevant_cases)
            else:
                return relevant_cases[0]

        return self.get_first_opened_case(referral_cases)

    def public_app_case(self, occurrence_case_id):
        try:
            self.person_case = get_person_case_from_occurrence(DOMAIN, occurrence_case_id)
        except ENikshayCaseNotFound:
            return False
        return super(Command, self).public_app_case(self.person_case)

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

    def close_cases(self, all_cases, occurrence_case_id, retain_case):
        # remove duplicates in case ids to remove so that we dont retain and close
        # the same case by mistake
        all_case_ids = set([case.case_id for case in all_cases])
        retain_case_id = retain_case.case_id
        case_ids_to_close = all_case_ids.copy()
        case_ids_to_close.remove(retain_case_id)

        case_accessor = CaseAccessors(DOMAIN)
        closing_extension_case_ids = case_accessor.get_extension_case_ids(case_ids_to_close)

        self.writerow({
            "occurrence_case_id": occurrence_case_id,
            "retain_case_id": retain_case_id,
            "closed_case_ids": ','.join(map(str, case_ids_to_close)),
            "closed_extension_case_ids": ','.join(map(str, closing_extension_case_ids)),
            "person_case_version": self.person_case.get_case_property('case_version'),
            "person_case_dataset": self.person_case.get_case_property('dataset')
        })
        if self.commit:
            updates = [(case_id, {'close_reason': "duplicate_reconciliation"}, True)
                       for case_id in case_ids_to_close]
            bulk_update_cases(DOMAIN, updates, self.__module__)


def get_open_referral_cases_from_occurrence(occurrence_case_id):
    case_accessor = CaseAccessors(DOMAIN)
    all_cases = case_accessor.get_reverse_indexed_cases([occurrence_case_id])
    return [case for case in all_cases
            if not case.closed and case.type == CASE_TYPE_REFERRAL]
