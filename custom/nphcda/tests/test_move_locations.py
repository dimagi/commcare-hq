import doctest
import tempfile
from contextlib import contextmanager
from inspect import cleandoc
from typing import Iterator
from unittest.mock import call, patch

from corehq.apps.hqcase.utils import CASEBLOCK_CHUNKSIZE
from corehq.apps.users.management.commands.nphcda_move_locations import (
    Settlement,
    SettlementPair,
    load_csv,
    submit_case_block_coro,
)


def test_load_csv():
    csv_content = cleandoc("""
        Username,Map from old location,,,,,Map to new location,,,,,Unmapped old locations,,,,,Unmapped new locations,,,,
        ,Scotland,Midlothian,Edinburgh,Craigleith,abc123,Scotland,Midlothian,Edinburgh,Inverleith,,,,,,,,,,,
        ,,,,,,,,,,,,,,,,,,,,
        """) + '\n'
    with get_temp_filename(csv_content) as csv_filename:
        location_pairs = list(load_csv(csv_filename))
    assert location_pairs == [
        SettlementPair(
            old_settlement=Settlement(
                state_name='Scotland',
                lga_name='Midlothian',
                ward_name='Edinburgh',
                settlement_name='Craigleith',
                location_id='abc123',
            ),
            new_settlement=Settlement(
                state_name='Scotland',
                lga_name='Midlothian',
                ward_name='Edinburgh',
                settlement_name='Inverleith',
                location_id=None,
            ),
        ),
    ]


def test_submit_case_block_coro():
    with patch(
        'corehq.apps.users.management.commands.nphcda_move_locations'
        '.submit_case_blocks'
    ) as mock_submit:

        with submit_case_block_coro('test-domain', dry_run=False) as submit_case_block:
            for i in range(CASEBLOCK_CHUNKSIZE + 1):
                submit_case_block.send(f'case_block_{i}')

            assert mock_submit.call_count == 1
            assert len(mock_submit.call_args[0][0]) == CASEBLOCK_CHUNKSIZE

        assert mock_submit.call_count == 2
        assert mock_submit.call_args == call(
            [f'case_block_{CASEBLOCK_CHUNKSIZE}'],
            'test-domain',
            device_id='corehq.apps.users.management.commands.nphcda_move_locations'
        )


def test_doctests():
    import corehq.apps.users.management.commands.nphcda_move_locations as module

    results = doctest.testmod(module)
    assert results.failed == 0


@contextmanager
def get_temp_filename(content: str) -> Iterator[str]:
    with tempfile.NamedTemporaryFile(mode='w', newline='') as temp_file:
        temp_file.write(content)
        temp_file.flush()
        yield temp_file.name
