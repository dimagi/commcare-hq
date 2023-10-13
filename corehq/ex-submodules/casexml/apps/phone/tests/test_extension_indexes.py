import json
import os.path
import re
import uuid
from itertools import count
from nose.tools import nottest

from casexml.apps.case.mock import CaseIndex, CaseStructure
from casexml.apps.phone.tests.test_sync_mode import BaseSyncTest
from corehq.form_processor.tests.utils import sharded
from corehq.util.test_utils import softer_assert


@nottest
def get_test_file_json(filename):
    base = os.path.dirname(__file__)
    file_path = 'data'
    path = os.path.join(base, file_path, '%s.json' % filename)
    with open(path, encoding='utf-8') as f:
        file_contents = f.read()

    return json.loads(file_contents)


@nottest
def get_test_name(test_name):
    return str("test_%s" % re.sub(r"\s", "_", test_name))


@nottest
def test_generator(skip=False, **test):
    @softer_assert()
    def test_func(self):
        if skip:
            self.skipTest(skip)
        self.build_case_structures(test)
        desired_cases = set(test.get('outcome', []))
        undesired_cases = self.get_all_case_names(test) - desired_cases

        sync_log = self.device.last_sync.get_log()
        self.assertEqual(
            desired_cases, sync_log.case_ids_on_phone,
            f'\nExpected: {desired_cases}\nActual: {sync_log.case_ids_on_phone}'
        )

        sync = self.device.sync(restore_id='')
        sync_cases = set(sync.cases)
        self.assertEqual(
            desired_cases, sync_cases,
            f'\nExpected: {desired_cases}\nActual: {sync_cases}'
        )
        self.assertFalse(
            undesired_cases & sync_cases,
            f'\nExpected missing: {undesired_cases}\nNot missing: {sync_cases}'
        )

    test_func.__name__ = get_test_name(test["name"])
    return test_func


@nottest
def assert_each_test_is_unique(tests_to_run):
    def make_signature(test):
        def rename(names, map={}, number=count()):
            for name in names:
                if name not in map:
                    map[name] = next(number)
                yield str(map[name])

        parts = []
        for key in SINGLES:
            if test.get(key):
                names = list(rename(test[key]))
                parts.append(key + ":" + ",".join(names))
        for key in PAIRS:
            if test.get(key):
                names = sorted("-".join(rename(pair)) for pair in test[key])
                parts.append(key + ":" + ",".join(names))
        return " ".join(parts)

    SINGLES = ["owned", "cases", "closed", "outcome"]
    PAIRS = ["subcases", "extensions"]
    ALL_FIELDS = set(SINGLES + PAIRS + ["name", "skip", "note"])
    seen = {}
    for test in tests_to_run:
        unknown = list(set(test) - ALL_FIELDS)
        assert not unknown, "bad fields {} in test: {}".format(unknown, test)
        sig = make_signature(test)
        assert sig not in seen, \
            "duplicate tests: %s, %s (%s)" % (test["name"], seen[sig], sig)
        seen[sig] = test["name"]


class TestSequenceMeta(type):

    def __new__(mcs, name, bases, dict):
        tests_to_run = get_test_file_json('case_relationship_tests')
        assert_each_test_is_unique(tests_to_run)
        run_single_tests = [t for t in tests_to_run if t.get('only', False)]
        if run_single_tests:
            tests_to_run = run_single_tests

        for test in tests_to_run:
            # Create a new testcase that the test runner is able to find
            test_name = get_test_name(test['name'])
            assert test_name not in dict, "duplicate test name: %s" % test_name
            dict[test_name] = test_generator(**test)

        return type.__new__(mcs, name, bases, dict)


@sharded
class IndexTreeTest(BaseSyncTest, metaclass=TestSequenceMeta):
    """Fetch all testcases from data/case_relationship_tests.json and run them

    Each testcase is structured as follows:
    {
        "name": The name of the test,
        "owned": Cases whose owner id is set to the user. Cases not in this list are owned by someone else,
        "subcases": [ A list of ordered pairs
            ["a","b"] means "a creates a child index pointing to b"
            or "a is a child of b"
        ],
        "extensions": [ A list of ordered pairs
            ["a","b"] means "a creates an extension index pointing to b"
            or "a is an extension of b"
        ],
        "closed": A list of the closed cases,
        "outcome": When syncing all the cases, which cases should be sent to the phone,
        "only": For debugging purposes, run a single test by adding 'only': true to those tests,
    }
    """

    def get_all_case_names(self, test):
        return set(
            [c for cc in test.get('subcases', []) for c in cc]
            + [e for ee in test.get('extensions', []) for e in ee]
            + test.get('owned', [])
            + test.get('closed', [])
            + test.get('outcome', [])
        )

    def build_case_structures(self, test):
        case_structures = []
        indices = {case: [] for case in self.get_all_case_names(test)}

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

        for case in self.get_all_case_names(test):
            case_structures.append(CaseStructure(
                attrs={
                    'create': True,
                    'owner_id': self.user.user_id if case in test.get('owned', []) else uuid.uuid4().hex,
                    'close': case in test.get('closed', []),
                },
                case_id=case,
                indices=indices[case],
            ))

        self.device.post_changes(case_structures)
