from __future__ import absolute_import
from __future__ import print_function

from corehq.apps.es import queries
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

from custom.enikshay.case_utils import (
    CASE_TYPE_TEST,
    get_occurrence_case_from_test,
    get_person_case_from_occurrence)
from custom.enikshay.const import (
    ENROLLED_IN_PRIVATE,
)
from custom.enikshay.management.commands.base_data_dump import BaseDataDump

DOMAIN = "enikshay"


class Command(BaseDataDump):
    """
    10. DST Test
    https://docs.google.com/spreadsheets/d/1OPp0oFlizDnIyrn7Eiv11vUp8IBmc73hES7qqT-mKKA/edit#gid=1526189801
    """
    TASK_NAME = "10_dst_tests"
    INPUT_FILE_NAME = "data_dumps_dst_tests.csv"

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.case_type = CASE_TYPE_TEST
        self.case_accessor = CaseAccessors(DOMAIN)

    def get_case_ids_query(self, case_type):
        """
        All open and closed test cases
        1) whose host/host = a person case (open or closed)
        with person.dataset = 'real' and self.enrolled_in_private != 'true' AND
        2)
        with self.test_type_value = 'fl_line_probe_assay'
        """
        return (self.case_search_instance
                .case_type(case_type)
                .case_property_query("test_type_value", "dst", clause=queries.MUST)
                )

    def include_case_in_dump(self, test_case):
        person = self.get_person(test_case)
        return (
            person and
            person.get_case_property('dataset') == 'real' and
            person.get_case_property(ENROLLED_IN_PRIVATE) != 'true'
        )

    def get_custom_value(self, column_name, test_case):
        if column_name == "Commcare UUID":
            return test_case.case_id
        elif column_name == "Date of Episode Creation":
            return self.get_episode(test_case).opened_on
        elif column_name == "Criteria for Testing":
            return (
                test_case.get_case_property('rft_drtb_diagnosis') or
                test_case.get_case_property('rft_drtb_diagnosis_ext_dst') or
                test_case.get_case_property('rft_drtb_follow_up') or
                test_case.get_case_property('rft_dstb_diagnosis') or
                test_case.get_case_property('rft_dstb_followup')
            )
        elif column_name == "R Result":
            if test_case.get_case_property('drug_resistance_list') == 'r':
                return 'resistant'
            elif test_case.get_case_property('drug_sensitive_list') == 'r':
                return 'sensitive'
            return 'no result'
        elif column_name == "H (inhA) Result":
            if test_case.get_case_property('drug_resistance_list') == 'h_inha':
                return 'resistant'
            elif test_case.get_case_property('drug_sensitive_list') == 'h_inha':
                return 'sensitive'
            return 'no result'
        elif column_name == "H (katG) Result":
            if test_case.get_case_property('drug_resistance_list') == 'h_katg':
                return 'resistant'
            elif test_case.get_case_property('drug_sensitive_list') == 'h_katg':
                return 'sensitive'
            return 'no result'
        elif column_name == "S Result":
            if test_case.get_case_property('drug_resistance_list') == 's':
                return 'resistant'
            elif test_case.get_case_property('drug_sensitive_list') == 's':
                return 'sensitive'
            return 'no result'
        elif column_name == "E Result":
            if test_case.get_case_property('drug_resistance_list') == 'e':
                return 'resistant'
            elif test_case.get_case_property('drug_sensitive_list') == 'e':
                return 'sensitive'
            return 'no result'
        elif column_name == "Z Result":
            if test_case.get_case_property('drug_resistance_list') == 'z':
                return 'resistant'
            elif test_case.get_case_property('drug_sensitive_list') == 'z':
                return 'sensitive'
            return 'no result'
        elif column_name == "SLID Drugs Result":
            if test_case.get_case_property('drug_resistance_list') == 'slid_class':
                return 'resistant'
            elif test_case.get_case_property('drug_sensitive_list') == 'slid_class':
                return 'sensitive'
            return 'no result'
        elif column_name == "Km Result":
            if test_case.get_case_property('drug_resistance_list') == 'km':
                return 'resistant'
            elif test_case.get_case_property('drug_sensitive_list') == 'km':
                return 'sensitive'
            return 'no result'
        elif column_name == "Cm Result":
            if test_case.get_case_property('drug_resistance_list') == 'cm':
                return 'resistant'
            elif test_case.get_case_property('drug_sensitive_list') == 'cm':
                return 'sensitive'
            return 'no result'
        elif column_name == "Am Result":
            if test_case.get_case_property('drug_resistance_list') == 'am':
                return 'resistant'
            elif test_case.get_case_property('drug_sensitive_list') == 'am':
                return 'sensitive'
            return 'no result'
        elif column_name == "FQ Drugs":
            if test_case.get_case_property('drug_resistance_list') == 'fq_class':
                return 'resistant'
            elif test_case.get_case_property('drug_sensitive_list') == 'fq_class':
                return 'sensitive'
            return 'no result'
        elif column_name == "Lfx Result":
            if test_case.get_case_property('drug_resistance_list') == 'lfx':
                return 'resistant'
            elif test_case.get_case_property('drug_sensitive_list') == 'lfx':
                return 'sensitive'
            return 'no result'
        elif column_name == "Mfx (0.5) Result":
            if test_case.get_case_property('drug_resistance_list') == 'mfx_05':
                return 'resistant'
            elif test_case.get_case_property('drug_sensitive_list') == 'mfx_05':
                return 'sensitive'
            return 'no result'
        elif column_name == "Mfx (2.0) Result":
            if test_case.get_case_property('drug_resistance_list') == 'mfx_02':
                return 'resistant'
            elif test_case.get_case_property('drug_sensitive_list') == 'mfx_02':
                return 'sensitive'
            return 'no result'
        elif column_name == "Eto Result":
            if test_case.get_case_property('drug_resistance_list') == 'eto':
                return 'resistant'
            elif test_case.get_case_property('drug_sensitive_list') == 'eto':
                return 'sensitive'
            return 'no result'
        elif column_name == "PAS Result":
            if test_case.get_case_property('drug_resistance_list') == 'pas':
                return 'resistant'
            elif test_case.get_case_property('drug_sensitive_list') == 'pas':
                return 'sensitive'
            return 'no result'
        elif column_name == "Lzd Result":
            if test_case.get_case_property('drug_resistance_list') == 'lzd':
                return 'resistant'
            elif test_case.get_case_property('drug_sensitive_list') == 'lzd':
                return 'sensitive'
            return 'no result'
        elif column_name == "Cfz":
            if test_case.get_case_property('drug_resistance_list') == 'cfz':
                return 'resistant'
            elif test_case.get_case_property('drug_sensitive_list') == 'cfz':
                return 'sensitive'
            return 'no result'
        elif column_name == "Clr":
            if test_case.get_case_property('drug_resistance_list') == 'clr':
                return 'resistant'
            elif test_case.get_case_property('drug_sensitive_list') == 'clr':
                return 'sensitive'
            return 'no result'
        elif column_name == "Azi":
            if test_case.get_case_property('drug_resistance_list') == 'azi':
                return 'resistant'
            elif test_case.get_case_property('drug_sensitive_list') == 'azi':
                return 'sensitive'
            return 'no result'
        elif column_name == "BDQ":
            if test_case.get_case_property('drug_resistance_list') == 'bdq':
                return 'resistant'
            elif test_case.get_case_property('drug_sensitive_list') == 'bdq':
                return 'sensitive'
            return 'no result'
        elif column_name == "DLM":
            if test_case.get_case_property('drug_resistance_list') == 'dlm':
                return 'resistant'
            elif test_case.get_case_property('drug_sensitive_list') == 'dlm':
                return 'sensitive'
            return 'no result'
        elif column_name == "Cs":
            if test_case.get_case_property('drug_resistance_list') == 'cs':
                return 'resistant'
            elif test_case.get_case_property('drug_sensitive_list') == 'cs':
                return 'sensitive'
            return 'no result'
        elif column_name == "Ofx":
            if test_case.get_case_property('drug_resistance_list') == 'ofx':
                return 'resistant'
            elif test_case.get_case_property('drug_sensitive_list') == 'ofx':
                return 'sensitive'
            return 'no result'
        elif column_name == "Amx/Clv":
            if test_case.get_case_property('drug_resistance_list') == 'amx_clv':
                return 'resistant'
            elif test_case.get_case_property('drug_sensitive_list') == 'amx_clv':
                return 'sensitive'
            return 'no result'
        elif column_name == "Test requested form submitted by - ID":
            return test_case.opened_by
        elif column_name == "Test Requested Form submitted By - User Name":
            user_id = None
            try:
                user_id = test_case.opened_by
                return CommCareUser.get_by_user_id(user_id, DOMAIN).username
            except Exception as e:
                return Exception("Could not get username. case opened by %s, %s" % (user_id, e))
        elif column_name == "Test Requested Form Submission Date":
            return test_case.opened_on
        elif column_name == "Test Resulted Form Submitted by (Name)":
            if test_case.get_case_property('result_recorded') == 'yes':
                user_id = self.case_property_change_info(test_case, "result_recorded", "yes").transaction.user_id
                return CommCareUser.get_by_user_id(user_id, DOMAIN).username
            else:
                return ''
        elif column_name == "Test Resulted Form Submitted by (ID)":
            if test_case.get_case_property('result_recorded') == 'yes':
                return self.case_property_change_info(test_case, "result_recorded", "yes").transaction.user_id
            else:
                return ''
        elif column_name == "Test Resulted Form Submission Date":
            if test_case.get_case_property('result_recorded') == 'yes':
                return self.case_property_change_info(test_case, "result_recorded", "yes").modified_on
            else:
                return ''
        return Exception("unknown custom column %s" % column_name)

    def get_person(self, test_case):
        if 'person' not in self.context:
            occurrence_case = self.get_occurrence(test_case)
            self.context['person'] = get_person_case_from_occurrence(DOMAIN, occurrence_case.case_id)
        if not self.context['person']:
            raise Exception("could not find person for test %s" % test_case.case_id)
        return self.context['person']

    def get_occurrence(self, test_case):
        if 'occurrence' not in self.context:
            self.context['occurrence'] = get_occurrence_case_from_test(DOMAIN, test_case.case_id)
        if not self.context['occurrence']:
            raise Exception("could not find occurrrence for test %s" % test_case.case_id)
        return self.context['occurrence']

    def get_episode(self, test_case):
        if 'episode' not in self.context:
            episode_case_id = test_case.get_case_property('episode_case_id')
            if not episode_case_id:
                raise Exception("episode case id not set for test %s" % test_case.case_id)
            self.context['episode'] = self.case_accessor.get_case(episode_case_id)
        if not self.context['episode']:
            raise Exception("could not find episode for test %s" % test_case.case_id)
        return self.context['episode']

    def get_case_reference_value(self, case_reference, test_case, calculation):
        if case_reference == 'person':
            return self.get_person(test_case).get_case_property(calculation)
        elif case_reference == 'episode':
            return self.get_episode(test_case).get_case_property(calculation)
        raise Exception("unknown case reference %s" % case_reference)
