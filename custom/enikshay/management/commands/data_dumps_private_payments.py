from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

from corehq.apps.locations.models import SQLLocation
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

from custom.enikshay.case_utils import (
    CASE_TYPE_TEST,
    CASE_TYPE_EPISODE,
    CASE_TYPE_OCCURRENCE,
    CASE_TYPE_PRESCRIPTION,
    CASE_TYPE_PERSON,
    CASE_TYPE_VOUCHER,
    get_first_parent_of_case,
)

from custom.enikshay.const import ENROLLED_IN_PRIVATE
from custom.enikshay.exceptions import ENikshayCaseNotFound
from custom.enikshay.management.commands.base_data_dump import BaseDataDump, PRIVATE_SECTOR_ID_MAPPING

DOMAIN = "enikshay"


class IncorrectVoucherType(Exception):
    pass


class Command(BaseDataDump):
    """ data dumps for private payments

    https://docs.google.com/spreadsheets/d/1t6cd-VPy6p8EOEhQJD15IbULU0EJ05ALQ0tcdfx6ng8/edit#gid=1577464442&range=A43
    """
    TASK_NAME = "07_private_payments"
    INPUT_FILE_NAME = "data_dumps_private_payments.csv"

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.case_type = CASE_TYPE_VOUCHER
        self.case_accessor = CaseAccessors(DOMAIN)

    def get_all_episode_cases(self, voucher_case):
        if 'all_episode_cases' not in self.context:
            occurrence_case = self.get_occurrence(voucher_case)
            self.context['all_episode_cases'] = [
                case for case in CaseAccessors(DOMAIN).get_reverse_indexed_cases(
                    [occurrence_case.case_id], case_types=[CASE_TYPE_EPISODE])
            ]
        if not self.context['all_episode_cases']:
            raise Exception("No episodes found for voucher %s" % voucher_case.case_id)
        return self.context['all_episode_cases']

    def get_custom_value(self, column_name, case):
        if column_name == "eNikshay person UUID":
            person_case = self.get_person(case)
            return person_case.case_id
        elif column_name == "eNikshay episode UUID":
            return ','.join([episode_case.case_id
                             for episode_case in self.get_all_episode_cases(case)])
        elif column_name == "Nikshay ID":
            return ','.join([episode_case.get_case_property('nikshay_id')
                             for episode_case in self.get_all_episode_cases(case)
                             if episode_case.get_case_property('nikshay_id')
                             ])
        elif column_name == "Organisation":
            owner_id = self.get_person(case).owner_id
            location = SQLLocation.active_objects.get_or_None(location_id=owner_id)
            if location:
                private_sector_org_id = location.metadata.get('private_sector_org_id')
                if private_sector_org_id:
                    return PRIVATE_SECTOR_ID_MAPPING.get(private_sector_org_id, private_sector_org_id)
                else:
                    raise Exception("Private Sector Organization ID not set for location %s" % owner_id)
            else:
                raise Exception("Location not found for id %s" % owner_id)
        elif column_name == "Approved Amount":
            if case.get_case_property('state') in ['paid', 'approved']:
                return case.get_case_property('amount_approved') or case.get_case_property('amount_fulfilled')
            else:
                return "not approved/paid, current state %s" % case.get_case_property('state')
        raise Exception("unknown custom column %s" % column_name)

    def get_case_ids_query(self, case_type):
        """
        ToDo: add date_fulfilled check in ES case ids query itself
        only those voucher cases
        date_fulfilled != null
        person.dataset = 'real'
        enrolled_in_private = 'true'
        """
        return (self.case_search_instance
                .case_type(case_type)
                )

    @staticmethod
    def _is_prescription_voucher(voucher_case):
        return voucher_case.get_case_property("voucher_type") == "prescription"

    @staticmethod
    def _is_lab_voucher(voucher_case):
        return voucher_case.get_case_property("voucher_type") == "test"

    def include_case_in_dump(self, voucher_case):
        if not voucher_case.get_case_property("date_fulfilled"):
            return False
        try:
            person = self.get_person(voucher_case)
        except ENikshayCaseNotFound as e:
            print("----ENikshayCaseNotFound----")
            print(e)
            print(voucher_case.case_id)
            print("-----------------------------")
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
            if self._is_prescription_voucher(voucher_case):
                episode_case = self.get_episode(voucher_case)
                occurrence_case = get_first_parent_of_case(episode_case.domain,
                                                           episode_case.case_id, CASE_TYPE_OCCURRENCE)
            elif self._is_lab_voucher(voucher_case):
                test_case = self.get_test(voucher_case)
                occurrence_case = get_first_parent_of_case(test_case.domain,
                                                           test_case.case_id, CASE_TYPE_OCCURRENCE)
            else:
                raise IncorrectVoucherType("Voucher id %s case neither lab or prescription" % voucher_case.case_id)
            self.context['occurrence'] = occurrence_case
        if not self.context['occurrence']:
            raise Exception("could not find occurrence for voucher %s" % voucher_case.case_id)
        return self.context['occurrence']

    def get_test(self, voucher_case):
        assert self._is_lab_voucher(voucher_case)
        if 'test' not in self.context:
            test_case = get_first_parent_of_case(voucher_case.domain, voucher_case.case_id,
                                                 CASE_TYPE_TEST)
            self.context['test'] = test_case
        if not self.context['test']:
            raise Exception("could not find test for lab voucher %s" % voucher_case.case_id)
        return self.context['test']

    def get_prescription(self, voucher_case):
        assert self._is_prescription_voucher(voucher_case)
        if 'prescription' not in self.context:
            prescription_case = get_first_parent_of_case(voucher_case.domain, voucher_case.case_id,
                                                         CASE_TYPE_PRESCRIPTION)
            self.context['prescription'] = prescription_case
        if not self.context['prescription']:
            raise Exception("could not find prescription for prescription voucher %s" % voucher_case.case_id)
        return self.context['prescription']

    def get_episode(self, voucher_case):
        assert self._is_prescription_voucher(voucher_case)
        if 'episode' not in self.context:
            host_case = self.get_prescription(voucher_case)
            episode_case = get_first_parent_of_case(host_case.domain, host_case.case_id,
                                                    CASE_TYPE_EPISODE)
            self.context['episode'] = episode_case
        if not self.context['episode']:
            raise Exception("could not find episode for voucher %s" % voucher_case.case_id)
        return self.context['episode']

    def get_case_reference_value(self, case_reference, test_case, calculation):
        if case_reference == 'person':
            return self.get_person(test_case).get_case_property(calculation)
        raise Exception("unknown case reference %s" % case_reference)
