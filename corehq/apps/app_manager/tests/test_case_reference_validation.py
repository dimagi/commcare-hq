import json
from corehq.apps.app_manager.views.forms import _get_case_references
from corehq.util.test_utils import generate_cases


@generate_cases([
    ({'load': {}},),
    ({'load': {'data/empty': []}},),
    ({'load': {'data/properties': ['p1', 'p2']}},),
    ({'load': {'data/multiple1': ['p1', 'p2'], 'data/multiple2': ['p1', 'p2']}},),
    ({'load': {}, 'save': {}},),
    ({'load': {}, 'save': {'data/empty': {}}},),
    ({'load': {}, 'save': {'data/case_type': {'case_type': 'ct'}}},),
    ({'load': {}, 'save': {'data/props': {'properties': ['p1', 'p2']}}},),
    ({'load': {}, 'save': {'data/create': {'create': True}}},),
    ({'load': {}, 'save': {'data/close': {'close': True}}},),
    ({
         'load': {
             'data/load1': ['p1', 'p2'],
             'data/load2': ['p1', 'p2']
         },
         'save': {
             'data/save1': {
                 'case_type': 'foo_type',
                 'properties': ['p1', 'p2'],
                 'create': True,
                 'close': True,
              },
             'data/save2': {
                 'case_type': 'foo_type',
                 'properties': ['p1', 'p2'],
                 'create': True,
                 'close': True,
              }
         }
     },),
])
def test_valid_args(self, case_references):
    wrapped_references = {
        'case_references': json.dumps(case_references)
    }
    self.assertEqual(case_references, _get_case_references(wrapped_references))


@generate_cases([
    ({},),
    ({'load': {'data/non-strings': [0, 'p2']}},),
    ({'load': {}, 'extra': 'stuff'},),
    ({'load': {}, 'save': {'data/extra': {'extra': 'stuff'}}},),
    ({'load': {}, 'save': {'data/non-strings': {'properties': [0, 'p2']}}},),
    ({'load': {}, 'save': {'data/create-non-bool': {'create': 'abc'}}},),
    ({'load': {}, 'save': {'data/close-non-bool': {'close': 0}}},),
])
def test_invalid_args(self, structure):
    with self.assertRaises(Exception):
        _get_case_references(structure)
