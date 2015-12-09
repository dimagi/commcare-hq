import re
from django.test import SimpleTestCase
from mock import Mock
import tasks


def iter_cases_to_modify():
    for domain in ('foo', 'bar', 'baz'):
        for case_id in ('ham', 'spam', 'eggs'):
            yield {
                'case_id': case_id,
                'update': {},
                'close': False,
            }, domain


def get_case_id(case_block):
    match = re.match(r'<case case_id="(\w+)"', case_block)
    if match:
        return match.group(1)


class NewUpdateCasePropertiesTest(SimpleTestCase):
    def test_chunk_size(self):
        """
        submit_case_blocks should be called with chunks of up to 2, and called when the domain changes
        """
        mock_iter_cases_to_modify = Mock(side_effect=iter_cases_to_modify)
        mock_submit_case_blocks = Mock()
        tasks.iter_cases_to_modify = mock_iter_cases_to_modify
        tasks.submit_case_blocks = mock_submit_case_blocks
        tasks.CASEBLOCK_CHUNKSIZE = 2

        tasks.new_update_case_properties()

        call_args_list = []
        for call_args in mock_submit_case_blocks.call_args_list:
            case_blocks = call_args[0][0]
            domain = call_args[0][1]
            case_ids = [get_case_id(case_block) for case_block in case_blocks]
            call_args_list.append((case_ids, domain))
        expected = [
            (['ham', 'spam'], 'foo'),
            (['eggs'], 'foo'),

            (['ham', 'spam'], 'bar'),
            (['eggs'], 'bar'),

            (['ham', 'spam'], 'baz'),
            (['eggs'], 'baz'),
        ]
        self.assertEqual(call_args_list, expected)
