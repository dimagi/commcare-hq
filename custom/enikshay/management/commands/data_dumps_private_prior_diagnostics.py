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
    CASE_TYPE_PERSON,
    CASE_TYPE_VOUCHER,
    get_first_parent_of_case,
)

from custom.enikshay.const import ENROLLED_IN_PRIVATE
from custom.enikshay.exceptions import ENikshayCaseNotFound
from custom.enikshay.management.commands.base_data_dump import BaseDataDump

DOMAIN = "enikshay"


class Command(BaseDataDump):
    """ data dumps for private prior diagnostics test cases

    https://docs.google.com/spreadsheets/d/1t6cd-VPy6p8EOEhQJD15IbULU0EJ05ALQ0tcdfx6ng8/edit#gid=378395348&range=A41
    """
    TASK_NAME = "03_private_prior_diagnostics"
    INPUT_FILE_NAME = "data_dumps_private_prior_diagnostics.csv"

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.case_type = CASE_TYPE_TEST
        self.case_accessor = CaseAccessors(DOMAIN)

    def get_custom_value(self, column_name, case):
        if column_name == "eNikshay person UUID":
            person_case = self.get_person(case)
            return person_case.case_id
        elif column_name == "eNikshay episode UUID":
            return ','.join([episode_case.case_id
                             for episode_case in self.get_all_episode_cases(case)])
        elif column_name == "Organisation":
            private_sector_organization_id = self.get_person(case).get_case_property(
                'private_sector_organization_id')
            if private_sector_organization_id:
                private_sector_organization = SQLLocation.active_objects.get_or_None(
                    location_id=private_sector_organization_id)
                if private_sector_organization:
                    return private_sector_organization.name
                else:
                    raise Exception("Could not find location with id %s" % private_sector_organization_id)
            else:
                raise Exception("Private sector org id not set for test %s" % case.case_id)
        elif column_name == "Nikshay ID":
            return ','.join([episode_case.get_case_property('nikshay_id')
                             for episode_case in self.get_all_episode_cases(case)
                             if episode_case.get_case_property('nikshay_id')
                             ])
        raise Exception("unknown custom column %s" % column_name)

    def get_case_ids_query(self, case_type):
        """
        only those test cases which do not have a voucher case associated with it
        person.dataset = 'real'
        enrolled_in_private = 'true'
        """
        return (self.case_search_instance
                .case_type(case_type)
                )

    @staticmethod
    def get_vouchers_from_test(test_case):
        return [
            case for case in CaseAccessors(DOMAIN).get_reverse_indexed_cases(
                [test_case.case_id], case_types=[CASE_TYPE_VOUCHER])
        ]

    def include_case_in_dump(self, test_case):
        try:
            person = self.get_person(test_case)
        except ENikshayCaseNotFound as e:
            print("----ENikshayCaseNotFound----")
            print(e.message)
            print(test_case.case_id)
            print("-----------------------------")
            return False
        return (
            person and
            person.get_case_property('dataset') == 'real' and
            person.get_case_property(ENROLLED_IN_PRIVATE) == 'true' and
            self.person_belongs_to_real_location(person) and
            not self.get_vouchers_from_test(test_case)
        )

    def get_person(self, test_case):
        if 'person' not in self.context:
            occurrence_case = self.get_occurrence(test_case)
            person_case = get_first_parent_of_case(occurrence_case.domain,
                                                   occurrence_case.case_id, CASE_TYPE_PERSON)
            self.context['person'] = person_case
        if not self.context['person']:
            raise Exception("could not find person for test %s" % test_case.case_id)
        return self.context['person']

    def get_occurrence(self, test_case):
        if 'occurrence' not in self.context:
            occurrence_case = get_first_parent_of_case(test_case.domain,
                                                       test_case.case_id, CASE_TYPE_OCCURRENCE)
            self.context['occurrence'] = occurrence_case
        if not self.context['occurrence']:
            raise Exception("could not find occurrrence for test %s" % test_case.case_id)
        return self.context['occurrence']

    def get_case_reference_value(self, case_reference, test_case, calculation):
        if case_reference == 'person':
            return self.get_person(test_case).get_case_property(calculation)
        raise Exception("unknown case reference %s" % case_reference)

    def get_all_episode_cases(self, test_case):
        if 'all_episode_cases' not in self.context:
            occurrence_case = self.get_occurrence(test_case)
            self.context['all_episode_cases'] = [
                case for case in CaseAccessors(DOMAIN).get_reverse_indexed_cases(
                    [occurrence_case.case_id], case_types=[CASE_TYPE_EPISODE])
            ]
        if not self.context['all_episode_cases']:
            raise Exception("No episodes found for test %s" % test_case.case_id)
        return self.context['all_episode_cases']
