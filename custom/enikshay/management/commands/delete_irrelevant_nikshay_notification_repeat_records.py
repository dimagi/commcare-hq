import csv
from datetime import datetime

from django.core.management.base import BaseCommand

from corehq.motech.repeaters.dbaccessors import iter_repeat_records_by_domain
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.case_utils import person_has_any_nikshay_notifiable_episode
from custom.enikshay.const import TREATMENT_INITIATED_IN_PHI


DOMAIN = "enikshay"
PATIENT_REGISTRATION_REPEATER_ID = "803b375da8d6f261777d339d12f89cdb"
HIV_TEST_REPEATER_ID = "8df1e819b5dcca25d1c38df0fa454768"
TREATMENT_REPEATER_ID = "6ea5977ec386c3e80a8cc400d832eff8"


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry_run',
            action='store_true',
        )
        parser.add_argument(
            'repeater'
        )

    def handle(self, repeater, *args, **options):
        self.dry_run = options.get('dry_run')
        self.result_file = "clean_up_stats_{ts}.csv".format(ts=datetime.now().strftime("%Y-%m-%d-%H-%M-%S"))
        with open(self.result_file, 'w') as output:
            self.writer = csv.DictWriter(output, fieldnames=['record_id', 'payload_id', 'failure_reason', 'attempts'])
            self.writer.writeheader()
            if repeater == "hiv_test":
                self.delete_irrelevant_hiv_test_repeat_records()
            elif repeater == "register_patient":
                self.delete_irrelevant_register_patient_repeat_records()
            elif repeater == "treatment_outcome":
                self.delete_irrelevant_treatment_outcome_repeat_records()

    def delete_repeat_record(self, repeat_record):
        self.add_row(repeat_record)
        if not self.dry_run:
            print("Deleting Repeat Record : %s" % repeat_record.get_id)
            repeat_record.delete()

    def add_row(self, repeat_record):
        self.writer.writerow({
            'record_id': repeat_record.get_id,
            'payload_id': repeat_record.payload_id,
            'failure_reason': repeat_record.failure_reason,
            'attempts': repeat_record.attempts
        })

    def delete_irrelevant_hiv_test_repeat_records(self):
        accessor = CaseAccessors(DOMAIN)
        for repeat_record in iter_repeat_records_by_domain(
            DOMAIN,
            repeater_id=HIV_TEST_REPEATER_ID,
            state="CANCELLED"
        ):
            person_case_id = repeat_record.payload_id
            person_case = accessor.get_case(person_case_id)
            if not person_has_any_nikshay_notifiable_episode(person_case):
                print("%s repeat record should be deleted" % repeat_record.get_id)
                print("Failure Reason: %s" % repeat_record.failure_reason)
                self.delete_repeat_record(repeat_record)

    def delete_irrelevant_treatment_outcome_repeat_records(self):
        accessor = CaseAccessors(DOMAIN)
        for repeat_record in iter_repeat_records_by_domain(
                DOMAIN,
                repeater_id=TREATMENT_REPEATER_ID,
                state="CANCELLED"
        ):
            episode_case_id = repeat_record.payload_id
            episode_case = accessor.get_case(episode_case_id)
            if episode_case.get_case_property("treatment_outcome_nikshay_registered") == "true":
                print("%s repeat record should be deleted" % repeat_record.get_id)
                self.delete_repeat_record(repeat_record)

    def delete_irrelevant_register_patient_repeat_records(self):
        accessor = CaseAccessors(DOMAIN)
        for repeat_record in iter_repeat_records_by_domain(
                DOMAIN,
                repeater_id=PATIENT_REGISTRATION_REPEATER_ID,
                state="CANCELLED"
        ):
            episode_case_id = repeat_record.payload_id
            episode_case = accessor.get_case(episode_case_id)
            if episode_case.get_case_property('treatment_initiated') != TREATMENT_INITIATED_IN_PHI:
                print("%s repeat record should be deleted" % repeat_record.get_id)
                print("Failure Reason: %s" % repeat_record.failure_reason)
                self.delete_repeat_record(repeat_record)
