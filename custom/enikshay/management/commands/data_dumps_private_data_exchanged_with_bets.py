from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

import json

from corehq.motech.repeaters.dbaccessors import get_repeat_records_by_payload_id
from custom.enikshay.case_utils import (
    CASE_TYPE_TEST,
    CASE_TYPE_EPISODE,
    CASE_TYPE_OCCURRENCE,
    CASE_TYPE_PERSON,
    CASE_TYPE_VOUCHER,
    CASE_TYPE_PRESCRIPTION,
    get_first_parent_of_case,
)

from custom.enikshay.const import ENROLLED_IN_PRIVATE
from custom.enikshay.management.commands.base_data_dump import BaseDataDump

DOMAIN = "enikshay"


class IncorrectVoucherType(Exception):
    pass


class Command(BaseDataDump):
    """ 13. data dumps for private data exchanged with BETS

    https://docs.google.com/spreadsheets/d/1t6cd-VPy6p8EOEhQJD15IbULU0EJ05ALQ0tcdfx6ng8/edit#gid=1056621161&range=A43
    """
    TASK_NAME = "13_private_data_exchanged_with_bets"
    INPUT_FILE_NAME = "data_dumps_private_data_exchanged_with_bets.csv"

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.case_type = CASE_TYPE_VOUCHER

    def get_bets_repeat_records(self, voucher_case):
        if 'bets_repeat_records' not in self.context:
            repeat_records = get_repeat_records_by_payload_id(voucher_case.domain, voucher_case.case_id)
            if not repeat_records:
                raise Exception("Found no repeat records for voucher %s" % voucher_case.case_id)
            self.context['bets_repeat_records'] = repeat_records
        return self.context['bets_repeat_records']

    def get_bets_repeat_record_payload(self, voucher_case):
        if 'bets_repeater_payload' not in self.context:
            repeat_records = self.get_bets_repeat_records(voucher_case)
            repeat_record = sorted(repeat_records, key=lambda x: x.last_checked, reverse=True)[0]
            self.context['bets_repeater_payload'] = json.loads(repeat_record.get_payload())['voucher_details'][0]
        return self.context['bets_repeater_payload']

    def get_custom_value(self, column_name, case):
        if column_name == "eNikshay person UUID":
            person_case = self.get_person(case)
            return person_case.case_id
        elif column_name == "eNikshay episode UUID":
            episode_case = self.get_episode(case)
            return episode_case.case_id
        elif column_name == "Event ID (as defined in BETS)":
            return self.get_bets_repeat_record_payload(case)['EventID']
        elif column_name == "Beneficiary Type (Lab or Chemist)":
            return self.get_bets_repeat_record_payload(case)['BeneficiaryType']
        elif column_name == "Enikshay Approver username":
            return self.get_bets_repeat_record_payload(case)['EnikshayApprover']
        elif column_name == "Enikshay Approver Role":
            return self.get_bets_repeat_record_payload(case)['EnikshayRole']
        elif column_name == "Status (Successfully sent to BETS or not)/Acknowledgement from BETS":
            return [{rr.get_id: rr.state} for rr in self.get_bets_repeat_records(case)]
        elif column_name == "Failure Description (if failed to send to BETS)":
            return [{rr.get_id: rr.failure_reason}
                    for rr in self.get_bets_repeat_records(case)
                    if rr.failure_reason
                    ]
        elif column_name == "Amount sent to BETS":
            return case.get_case_property('amount_approved') or case.get_case_property('amount_fulfilled')
        elif column_name == "Date when sent to BETS":
            all_attempts_datetime = {}
            for repeat_record in self.get_bets_repeat_records(case):
                attempts = repeat_record.attempts
                all_attempts_datetime[repeat_record.get_id] = [str(attempt.datetime) for attempt in attempts]
            return all_attempts_datetime
        raise Exception("unknown custom column %s" % column_name)

    def get_case_ids_query(self, case_type):
        """
        voucher_approval_status = approved
        person.dataset = 'real'
        person.enrolled_in_private = 'true'
        """
        return (self.case_search_instance
                .case_type(case_type)
                .case_property_query("voucher_approval_status", "approved")
                )

    @staticmethod
    def _is_prescription_voucher(voucher_case):
        return voucher_case.get_case_property("voucher_type") == "prescription"

    @staticmethod
    def _is_lab_voucher(voucher_case):
        return voucher_case.get_case_property("voucher_type") == "lab"

    def include_case_in_dump(self, voucher_case):
        try:
            person = self.get_person(voucher_case)
        except IncorrectVoucherType:
            return False
        return (
            person and
            person.get_case_property('dataset') == 'real' and
            person.get_case_property(ENROLLED_IN_PRIVATE) == 'true' and
            self.person_belongs_to_real_location(person)
        )

    def get_person(self, voucher_case):
        if 'person' not in self.context:
            occurrence_case = self.get_occurrence(voucher_case)
            person_case = get_first_parent_of_case(occurrence_case.domain,
                                                   occurrence_case.case_id, CASE_TYPE_PERSON)
            self.context['person'] = person_case
        if not self.context['person']:
            raise Exception("could not find person for voucher %s" % voucher_case.case_id)
        return self.context['person']

    def get_occurrence(self, voucher_case):
        if 'occurrence' not in self.context:
            episode_case = self.get_episode(voucher_case)
            occurrence_case = get_first_parent_of_case(episode_case.domain,
                                                       episode_case.case_id, CASE_TYPE_OCCURRENCE)
            self.context['occurrence'] = occurrence_case
        if not self.context['occurrence']:
            raise Exception("could not find occurrence for voucher %s" % voucher_case.case_id)
        return self.context['occurrence']

    def get_prescription(self, voucher_case):
        assert self._is_prescription_voucher(voucher_case)
        if 'prescription' not in self.context:
            prescription_case = get_first_parent_of_case(voucher_case.domain, voucher_case.case_id,
                                                         CASE_TYPE_PRESCRIPTION)
            self.context['prescription'] = prescription_case
        if not self.context['prescription']:
            raise Exception("could not find prescription for prescription voucher %s" % voucher_case.case_id)
        return self.context['prescription']

    def get_test(self, voucher_case):
        if not self.context['test']:
            test_case = get_first_parent_of_case(voucher_case.domain, voucher_case.case_id,
                                                 CASE_TYPE_TEST)
            self.context['test'] = test_case
        if not self.context['test']:
            raise Exception("could not find test for lab voucher %s" % voucher_case.case_id)
        return self.context['test']

    def get_episode(self, voucher_case):
        if 'episode' not in self.context:
            if self._is_prescription_voucher(voucher_case):
                host_case = self.get_prescription(voucher_case)
            elif self._is_lab_voucher(voucher_case):
                host_case = self.get_test(voucher_case)
            else:
                raise IncorrectVoucherType("Voucher id %s case neither lab or prescription" % voucher_case.case_id)
            episode_case = get_first_parent_of_case(host_case.domain, host_case.case_id,
                                                    CASE_TYPE_EPISODE)
            self.context['episode'] = episode_case
        if not self.context['episode']:
            raise Exception("could not find episode for voucher %s" % voucher_case.case_id)
        return self.context['episode']

    def get_case_reference_value(self, case_reference, voucher_case, calculation):
        if case_reference == 'person':
            return self.get_person(voucher_case).get_case_property(calculation)
        raise Exception("unknown case reference %s" % case_reference)
