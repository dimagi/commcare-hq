from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.xml import V2
from corehq.apps.callcenter.indicator_sets import AAROHI_MOTHER_FORM, CallCenterV2
from corehq.apps.callcenter.utils import sync_user_cases
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.callcenter.tests.sql_fixture import load_data, load_custom_data
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.models import CommCareUser
from django.test import TestCase


def create_domain_and_user(domain_name, username):
    domain = create_domain(domain_name)
    user = CommCareUser.create(domain_name, username, '***')

    domain.call_center_config.enabled = True
    domain.call_center_config.case_owner_id = user.user_id
    domain.call_center_config.case_type = 'cc_flw'
    domain.save()

    sync_user_cases(user)
    return domain, user


def get_indicators(prefix, values, infix=None, is_legacy=False):
    ranges = ['week0', 'week1', 'month0', 'month1']
    data = {}
    separator = '' if is_legacy else '_'
    infix = '{}{}{}'.format(separator, infix, separator) if infix else separator
    for i, r in enumerate(ranges):
        r = r.title() if is_legacy else r
        indicator_name = '{prefix}{infix}{suffix}'.format(
            prefix=prefix,
            infix=infix,
            suffix=r)
        data[indicator_name] = values[i]

    return data


class CallCenterTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cc_domain, cls.cc_user = create_domain_and_user('callcentertest', 'user1')
        load_data(cls.cc_domain.name, cls.cc_user.user_id)

        cls.aarohi_domain, cls.aarohi_user = create_domain_and_user('aarohi', 'user2')
        load_custom_data(cls.aarohi_domain.name, cls.aarohi_user.user_id, xmlns=AAROHI_MOTHER_FORM)

        # create one case of each type so that we get the indicators where there is no data for the period
        submit_case_blocks(
            CaseBlock(
                create=True,
                case_id='person1',
                case_type='person',
                user_id='user1',
                version=V2,
            ).as_string(), 'callcentertest')

        submit_case_blocks(
            CaseBlock(
                create=True,
                case_id='dog1',
                case_type='dog',
                user_id='user1',
                version=V2,
            ).as_string(), 'callcentertest')

    @classmethod
    def tearDownClass(cls):
        cls.cc_domain.delete()
        cls.aarohi_domain.delete()

    def _test_indicators(self, domain, user, expected):
        indicator_set = CallCenterV2(domain, user)
        data = indicator_set.get_data()
        case_id = indicator_set.user_to_case_map[user.user_id]
        self.assertIn(case_id, data)
        user_data = data[case_id]

        mismatches = []
        for k, v in expected.items():
            expected_value = user_data.pop(k)
            if expected_value != v:
                mismatches.append('{}: {} != {}'.format(k, v, expected_value))

        if mismatches:
            self.fail('Mismatching indicators:\n{}'.format('\t\n'.join(mismatches)))

        if user_data:
            self.fail('Additional indicators:\n{}'.format('\t\n'.join(user_data.keys())))

    def test_standard_indicators(self):
        expected = {'totalCases': 5L}
        expected.update(get_indicators('formsSubmitted', [2L, 4L, 7L, 0L], is_legacy=True))
        expected.update(get_indicators('forms_submitted', [2L, 4L, 7L, 0L]))
        expected.update(get_indicators('casesUpdated', [0L, 1L, 3L, 5L], is_legacy=True))
        expected.update(get_indicators('cases_total', [4L, 4L, 6L, 5L]))
        expected.update(get_indicators('cases_total', [1L, 1L, 3L, 0L], infix='person'))
        expected.update(get_indicators('cases_total', [3L, 3L, 3L, 5L], infix='dog'))
        expected.update(get_indicators('cases_opened', [0L, 1L, 3L, 5L]))
        expected.update(get_indicators('cases_opened', [0L, 1L, 3L, 0L], infix='person'))
        expected.update(get_indicators('cases_opened', [0L, 0L, 0L, 5L], infix='dog'))
        expected.update(get_indicators('cases_closed', [0L, 0L, 2L, 2L]))
        expected.update(get_indicators('cases_closed', [0L, 0L, 2L, 0L], infix='person'))
        expected.update(get_indicators('cases_closed', [0L, 0L, 0L, 2L], infix='dog'))
        expected.update(get_indicators('cases_active', [0L, 1L, 3L, 5L]))
        expected.update(get_indicators('cases_active', [0L, 1L, 3L, 0L], infix='person'))
        expected.update(get_indicators('cases_active', [0L, 0L, 0L, 5L], infix='dog'))

        self._test_indicators(self.cc_domain, self.cc_user, expected)

    def test_custom_indicators(self):
        expected = {'totalCases': 0L}
        expected.update(get_indicators('formsSubmitted', [3L, 3L, 9L, 0L], is_legacy=True))
        expected.update(get_indicators('forms_submitted', [3L, 3L, 9L, 0L]))
        expected.update(get_indicators('casesUpdated', [0L, 0L, 0L, 0L], is_legacy=True))
        expected.update(get_indicators('cases_total', [0L, 0L, 0L, 0L]))
        expected.update(get_indicators('cases_opened', [0L, 0L, 0L, 0L]))
        expected.update(get_indicators('cases_closed', [0L, 0L, 0L, 0L]))
        expected.update(get_indicators('cases_active', [0L, 0L, 0L, 0L]))

        # custom
        expected.update(get_indicators('motherForms', [3L, 3L, 9L, 0L], is_legacy=True))
        expected.update(get_indicators('childForms', [0L, 0L, 0L, 0L], is_legacy=True))
        expected.update(get_indicators('motherDuration', [3L, 4L, 4L, 0L], is_legacy=True))

        self._test_indicators(self.aarohi_domain, self.aarohi_user, expected)
