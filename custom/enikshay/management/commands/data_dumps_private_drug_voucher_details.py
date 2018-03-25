from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

from custom.enikshay.case_utils import (
    CASE_TYPE_EPISODE,
    CASE_TYPE_OCCURRENCE,
    CASE_TYPE_PRESCRIPTION,
    CASE_TYPE_PERSON,
    CASE_TYPE_VOUCHER,
    get_first_parent_of_case,
)

from custom.enikshay.const import ENROLLED_IN_PRIVATE
from custom.enikshay.management.commands.base_data_dump import BaseDataDump

DOMAIN = "enikshay"


class Command(BaseDataDump):
    """ data dumps for private drug voucher details

    https://docs.google.com/spreadsheets/d/1t6cd-VPy6p8EOEhQJD15IbULU0EJ05ALQ0tcdfx6ng8/edit#gid=1394378210&range=A42
    """
    TASK_NAME = "06_private_drug_voucher_details"
    INPUT_FILE_NAME = "data_dumps_private_drug_voucher_details.csv"

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.case_type = CASE_TYPE_PRESCRIPTION
        self.case_accessor = CaseAccessors(DOMAIN)

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
        only those prescription cases
        person.dataset = 'real'
        enrolled_in_private = 'true'
        """
        return (self.case_search_instance
                .case_type(case_type)
                )

    def include_case_in_dump(self, test_case):
        person = self.get_person(test_case)
        return (
            person and
            person.get_case_property('dataset') == 'real' and
            person.get_case_property(ENROLLED_IN_PRIVATE) == 'true'
        )

    def get_voucher(self, prescription_case):
        if 'voucher' not in self.context:
            voucher_cases = self.case_accessor.get_reverse_indexed_cases(
                [prescription_case.case_id], case_types=[CASE_TYPE_VOUCHER])
            if len(voucher_cases) > 1:
                raise Exception("Multiple voucher cases found for prescription %s" % prescription_case.case_id)
            elif len(voucher_cases) == 1:
                self.context['voucher'] = voucher_cases[0]
            else:
                self.context['voucher'] = None
        if not self.context['voucher']:
            raise Exception("No voucher cases found for prescription %s" % prescription_case.case_id)
        return self.context['voucher']

    def get_person(self, prescription_case):
        if 'person' not in self.context:
            occurrence_case = self.get_occurrence(prescription_case)
            person_case = get_first_parent_of_case(occurrence_case.domain,
                                                   occurrence_case.case_id, CASE_TYPE_PERSON)
            self.context['person'] = person_case
        if not self.context['person']:
            raise Exception("could not find person for prescription %s" % prescription_case.case_id)
        return self.context['person']

    def get_occurrence(self, prescription_case):
        if 'occurrence' not in self.context:
            episode_case = self.get_episode(prescription_case)
            occurrence_case = get_first_parent_of_case(episode_case.domain,
                                                       episode_case.case_id, CASE_TYPE_OCCURRENCE)
            self.context['occurrence'] = occurrence_case
        if not self.context['occurrence']:
            raise Exception("could not find occurrence for prescription %s" % prescription_case.case_id)
        return self.context['occurrence']

    def get_episode(self, prescription_case):
        if 'episode' not in self.context:
            episode_case = get_first_parent_of_case(prescription_case.domain, prescription_case.case_id,
                                                    CASE_TYPE_EPISODE)
            self.context['episode'] = episode_case
        if not self.context['episode']:
            raise Exception("could not find episode for prescription %s" % prescription_case.case_id)
        return self.context['episode']

    def get_case_reference_value(self, case_reference, test_case, calculation):
        if case_reference == 'person':
            return self.get_person(test_case).get_case_property(calculation)
        elif case_reference == 'episode':
            return self.get_episode(test_case).get_case_property(calculation)
        elif case_reference == "voucher":
            return self.get_voucher(test_case).get_case_property(calculation)
        raise Exception("unknown case reference %s" % case_reference)
