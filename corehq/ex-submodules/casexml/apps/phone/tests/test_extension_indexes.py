import json
import os.path
import uuid
from nose.tools import nottest

import re
from casexml.apps.case.mock import CaseIndex, CaseStructure
from casexml.apps.case.tests.util import assert_user_doesnt_have_cases, \
    assert_user_has_cases
from casexml.apps.phone.models import get_properly_wrapped_sync_log
from casexml.apps.phone.tests.test_sync_mode import SyncBaseTest
from corehq.form_processor.tests import run_with_all_backends
from corehq.util.test_utils import softer_assert


@nottest
def get_test_file_json(filename):
    base = os.path.dirname(__file__)
    file_path = 'data'
    path = os.path.join(base, file_path, '%s.json' % filename)
    with open(path) as f:
        file_contents = f.read()

    return json.loads(file_contents)


@nottest
def test_generator(test_name, skip=False):
    @softer_assert
    def test(self):
        if skip:
            self.skipTest(skip)
        self.build_case_structures(test_name)
        desired_cases = self._get_test(test_name).get('outcome', [])
        undesired_cases = [case for case in self.ALL_CASES if case not in desired_cases]
        sync_log = get_properly_wrapped_sync_log(self.sync_log._id)
        self.assertEqual(sync_log.case_ids_on_phone, set(desired_cases))
        assert_user_has_cases(self, self.user, desired_cases)
        assert_user_doesnt_have_cases(self, self.user, undesired_cases)
    return run_with_all_backends(test)


class TestSequenceMeta(type):
    def __new__(mcs, name, bases, dict):
        tests_to_run = get_test_file_json('case_relationship_tests')
        run_single_tests = filter(lambda t: t.get('only', False), tests_to_run)
        if run_single_tests:
            tests_to_run = run_single_tests

        for test in [(test['name'], test.get('skip', False)) for test in tests_to_run]:
            # Create a new testcase that the test runner is able to find
            dict["test_%s" % re.sub("\s", "_", test[0])] = test_generator(test[0], test[1])

        return type.__new__(mcs, name, bases, dict)


class IndexTreeTest(SyncBaseTest):
    """Fetch all testcases from data/case_relationship_tests.json and run them

    Each testcase is structured as follows:
    {
        "name": The name of the test,
        "owned": Cases whose owner id is set to the user. Cases not in this list are owned by someone else,
        "subcases": [ A list of ordered pairs e.g. ["a","b"] means "a creates a child index pointing to b"],
        "extensions": [ A list of ordered pairs e.g. ["a","b"] means "a creates an extension index pointing to b"],
        "closed": A list of the closed cases,
        "outcome": When syncing all the cases, which cases should be sent to the phone,
        "only": For debugging purposes, run a single test by adding 'only': true to those tests,
    }
    """
    __metaclass__ = TestSequenceMeta

    ALL_CASES = ['a', 'b', 'c', 'd', 'e']

    @property
    def all_tests(self):
        """All the test cases in a dict"""
        all_tests = {}
        tests = get_test_file_json('case_relationship_tests')
        for test in tests:
            all_tests[test['name']] = test
        return all_tests

    def _get_test(self, test_name):
        return self.all_tests[test_name]

    def build_case_structures(self, test_name):
        test = self._get_test(test_name)
        case_structures = []
        indices = {case: [] for case in self.ALL_CASES}

        for i, subcase in enumerate(test.get('subcases', [])):
            indices[subcase[0]].append(CaseIndex(
                related_structure=CaseStructure(
                    attrs={
                        'create': False,
                        'owner_id': self.user.user_id if subcase[1] in test.get('owned', []) else uuid.uuid4().hex,
                        'close': subcase[1] in test.get('closed', []),
                    },
                    case_id=subcase[1],
                ),
                relationship='child',
                identifier='child_{}'.format(i),
            ))

        for i, extension in enumerate(test.get('extensions', [])):
            indices[extension[0]].append(CaseIndex(
                related_structure=CaseStructure(
                    attrs={
                        'create': False,
                        'owner_id': (self.user.user_id if extension[1]
                                     in test.get('owned', []) else uuid.uuid4().hex),
                        'close': extension[1] in test.get('closed', []),
                    },
                    case_id=extension[1],
                ),
                relationship='extension',
                identifier='extension_{}'.format(i),
            ))

        for case in self.ALL_CASES:
            case_structures.append(CaseStructure(
                attrs={
                    'create': True,
                    'owner_id': self.user.user_id if case in test.get('owned', []) else uuid.uuid4().hex,
                    'close': case in test.get('closed', []),
                },
                case_id=case,
                indices=indices[case],
            ))

        self.factory.create_or_update_cases(case_structures)
