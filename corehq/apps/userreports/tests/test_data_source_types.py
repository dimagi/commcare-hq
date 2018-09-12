from corehq.apps.userreports.const import DATA_SOURCE_TYPE_AGGREGATE, DATA_SOURCE_TYPE_STANDARD
from corehq.apps.userreports.models import guess_data_source_type
from corehq.util.test_utils import generate_cases


@generate_cases([
    ('bbfcfa3601a542f79ebece7867fe07a8', DATA_SOURCE_TYPE_STANDARD),
    ('ed4e3670-9f4a-481f-9870-b0c94c263df5', DATA_SOURCE_TYPE_STANDARD),
    ('static-some-static-data-source-id', DATA_SOURCE_TYPE_STANDARD),
    ('1', DATA_SOURCE_TYPE_AGGREGATE),
    (1, DATA_SOURCE_TYPE_AGGREGATE),
    ('abcd', DATA_SOURCE_TYPE_STANDARD),
])
def test_guess_type(self, data_source_id, expected_type):
    self.assertEqual(expected_type, guess_data_source_type(data_source_id))
