from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)


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


class Command(BaseDataDump):
    """ 13. data dumps for private data exchanged with BETS

    https://docs.google.com/spreadsheets/d/1t6cd-VPy6p8EOEhQJD15IbULU0EJ05ALQ0tcdfx6ng8/edit#gid=1056621161&range=A43
    """
    TASK_NAME = "13_private_data_exchanged_with_bets"
    INPUT_FILE_NAME = "data_dumps_private_data_exchanged_with_bets.csv"

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.case_type = CASE_TYPE_VOUCHER

    def get_custom_value(self, column_name, case):
        if column_name == "eNikshay person UUID":
            person_case = self.get_person(case)
            return person_case.case_id
        elif column_name == "eNikshay episode UUID":
            episode_case = self.get_episode(case)
            return episode_case.case_id
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
        person = self.get_person(voucher_case)
        return (
            person and
            person.get_case_property('dataset') == 'real' and
            person.get_case_property(ENROLLED_IN_PRIVATE) == 'true'
        )

    def get_person(self, voucher_case):
        if 'person' not in self.context:
            occurrence_case = self.get_occurrence(voucher_case)
            person_case = get_first_parent_of_case(occurrence_case.domain, occurrence_case.case_id, CASE_TYPE_PERSON)
            self.context['person'] = person_case
        if not self.context['person']:
            raise Exception("could not find person for voucher %s" % voucher_case.case_id)
        return self.context['person']

    def get_occurrence(self, voucher_case):
        if 'occurrence' not in self.context:
            episode_case = self.get_episode(voucher_case)
            occurrence_case = get_first_parent_of_case(episode_case.domain, episode_case.case_id, CASE_TYPE_OCCURRENCE)
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
                raise Exception("Voucher id %s case neither lab or prescription" % voucher_case.case_id)
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
