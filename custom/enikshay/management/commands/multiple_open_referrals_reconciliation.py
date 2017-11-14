import csv

from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.mail import EmailMessage

from corehq.apps.hqcase.utils import bulk_update_cases
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import CommCareCaseSQL
from custom.enikshay.case_utils import (
    get_person_case_from_occurrence,
    CASE_TYPE_REFERRAL,
)
from custom.enikshay.const import (
    ENROLLED_IN_PRIVATE,
)
from custom.enikshay.exceptions import ENikshayCaseNotFound

DOMAIN = "enikshay"


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--dry_run', action='store_true')
        parser.add_argument('--recipient', type=str)

    def handle(self, *args, **options):
        # self.dry_run = options.get('dry_run')
        self.dry_run = True
        self.recipient = options.get('recipient', 'mkangia@dimagi.com')
        self.recipient = list(self.recipient) if not isinstance(self.recipient, basestring) else [self.recipient]
        self.result_file_name = self.setup_result_file()
        # iterate all occurrence cases
        for occurrence_case_id in self._get_open_occurrence_case_ids_to_process():
            if self.public_app_case(occurrence_case_id):
                referral_cases = get_open_referral_cases_from_occurrence(occurrence_case_id)
                if len(referral_cases) > 1:
                    self.reconcile_cases(referral_cases, occurrence_case_id)
        self.email_report()

    def email_report(self):
        csvfile = open(self.result_file_name)
        email = EmailMessage(
            subject="Multiple Open Referrals Reconciliation Report",
            body="Please find attached report for a %s run finished at %s." %
                 ('dry' if self.dry_run else 'real', datetime.now()),
            to=self.recipient,
            from_email=settings.DEFAULT_FROM_EMAIL
        )
        email.attach(filename=self.result_file_name, content=csvfile.read())
        csvfile.close()
        email.send()

    @staticmethod
    def get_result_file_headers():
        return [
            "occurrence_case_id",
            "retain_case_id",
            "closed_case_ids",
            "notes"
        ]

    def setup_result_file(self):
        file_name = "multiple_open_referrals_reconciliation_report_{timestamp}.csv".format(
            timestamp=datetime.now().strftime("%Y-%m-%d-%H-%M-%S"),
        )
        with open(file_name, 'w') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.get_result_file_headers())
            writer.writeheader()
        return file_name

    def writerow(self, row):
        with open(self.result_file_name, 'a') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.get_result_file_headers())
            writer.writerow(row)

    def reconcile_cases(self, referral_cases, occurrence_case_id):
        retain_case = sorted(referral_cases, key=lambda x: x.opened_on)[0]
        self.close_cases(referral_cases, occurrence_case_id, retain_case)

    def public_app_case(self, occurrence_case_id):
        try:
            person_case = get_person_case_from_occurrence(DOMAIN, occurrence_case_id)
        except ENikshayCaseNotFound:
            self.writerow({
                "occurrence_case_id": occurrence_case_id,
                "notes": "person case not found",
            })
            return False
        if person_case.get_case_property(ENROLLED_IN_PRIVATE) == 'true':
            return False
        return True

    @staticmethod
    def _get_open_occurrence_case_ids_to_process():
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
            print("processing %d docs from db %s" % (num_case_ids, db))
            for i, case_id in enumerate(case_ids):
                yield case_id
                if i % 1000 == 0:
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
            "closed_extension_case_ids": ','.join(map(str, closing_extension_case_ids))
        })
        if not self.dry_run:
            updates = [(case_id, {'close_reason': "duplicate_reconciliation"}, True)
                       for case_id in case_ids_to_close]
            bulk_update_cases(DOMAIN, updates, self.__module__)


def get_open_referral_cases_from_occurrence(occurrence_case_id):
    case_accessor = CaseAccessors(DOMAIN)
    all_cases = case_accessor.get_reverse_indexed_cases([occurrence_case_id])
    return [case for case in all_cases
            if not case.closed and case.type == CASE_TYPE_REFERRAL]
