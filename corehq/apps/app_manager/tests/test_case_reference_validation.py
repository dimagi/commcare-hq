import json
from corehq.apps.app_manager.views.forms import _get_case_references
from corehq.util.test_utils import generate_cases


@generate_cases([
    ({'load': {}},),
    ({'load': {'data/empty': []}},),
    ({'load': {'data/multiple': ['p1', 'p2']}},),
])
def test_valid_args(self, case_references):
    wrapped_references = {
        'case_references': json.dumps(case_references)
    }
    self.assertEqual(case_references, _get_case_references(wrapped_references))


@generate_cases([
    ({},),
    ({'load': {'data/non-strings': [0, 'p2']}},),
    ({'load': {}, 'extra': {}},),
])
def test_invalid_args(self, structure):
    with self.assertRaises(Exception):
        _get_case_references(structure)
