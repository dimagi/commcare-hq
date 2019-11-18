from corehq.apps.userreports.operators import get_operator
from corehq.util.test_utils import generate_cases


@generate_cases((
    ('a', [], False),
    ('a', ['a'], True),
    ('a', ['a', 'b'], True),
    ('a', 'basic', True),
    ('d', 'basic', False),
    (None, [], False),
    (None, None, False),
    ('a', None, False),
    (42, [42], True),
    (42, 42, False),
    (42, ['42'], False),
))
def test_in_operator(self, input, reference_list, expected_result):
    self.assertEqual(expected_result, get_operator('in')(input, reference_list))
