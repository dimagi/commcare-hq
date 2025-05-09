import doctest
from inspect import cleandoc
from unittest.mock import call, patch

from corehq.apps.users.management.commands.nphcda_find_mismatches import (
    UserChanges,
)
from corehq.apps.users.management.commands.nphcda_move_users_cases import (
    CASE_BLOCK_COUNT,
    load_csv,
    load_yaml,
    move_case_block_coro,
)

from .contextmanagers import get_temp_filename


def test_yaml_input():
    yaml_content = cleandoc("""
        location_map:
          abc123: def456
        unmapped_new_locations: []
        unmapped_old_locations: []
        username: fo/baz001
        ---
        location_map: {}
        unmapped_new_locations: []
        unmapped_old_locations:
        - abc123
        username: fo/baz002
        ---
        location_map: {}
        unmapped_new_locations:
        - def456
        unmapped_old_locations: []
        username: fo/baz003
        ---
        location_map:
          abc123: def456
        unmapped_new_locations:
        - def789
        unmapped_old_locations:
        - abc456
        username: fo/baz004
        """) + '\n'
    with get_temp_filename(yaml_content) as yaml_filename:
        user_changes = list(load_yaml(yaml_filename))
    assert user_changes == [
        UserChanges(
            username='fo/baz001',
            location_map={'abc123': 'def456'},
            unmapped_old_locations=[],
            unmapped_new_locations=[],
        ),
        UserChanges(
            username='fo/baz002',
            location_map={},
            unmapped_old_locations=['abc123'],
            unmapped_new_locations=[],
        ),
        UserChanges(
            username='fo/baz003',
            location_map={},
            unmapped_old_locations=[],
            unmapped_new_locations=['def456'],
        ),
        UserChanges(
            username='fo/baz004',
            location_map={'abc123': 'def456'},
            unmapped_old_locations=['abc456'],
            unmapped_new_locations=['def789'],
        ),
    ]


def test_load_csv():
    csv_content = cleandoc("""
        Username,Map from old location,,,,,Map to new location,,,,,Unmapped old locations,,,,,Unmapped new locations,,,,
        fo/baz001,Scotland,Midlothian,Edinburgh,Craigleith,abc123,Scotland,Midlothian,Edinburgh,Inverleith,def456,,,,,,,,,,
        fo/baz001,,,,,,,,,,,Scotland,Fife,Inverkeithing,Inverkeithing,abc456,,,,,
        fo/baz001,,,,,,,,,,,,,,,,Scotland,Midlothian,Edinburgh,Leith,def789
        fo/baz001,,,,,,,,,,,,,,,,,,,,
        fo/baz002,Scotland,Midlothian,Edinburgh,Craigleith,abc123,Scotland,Midlothian,Edinburgh,Inverleith,def456,,,,,,,,,,
        fo/baz003,,,,,,,,,,,Scotland,Fife,Inverkeithing,Inverkeithing,abc456,,,,,
        fo/baz004,,,,,,,,,,,,,,,,Scotland,Midlothian,Edinburgh,Leith,def789
        fo/baz005,,,,,,,,,,,,,,,,,,,,
        """) + '\n'
    with get_temp_filename(csv_content) as csv_filename:
        user_changes = list(load_csv(csv_filename))
    assert user_changes == [
        UserChanges(
            username='fo/baz001',
            location_map={'abc123': 'def456'},
            unmapped_old_locations=['abc456'],
            unmapped_new_locations=['def789'],
        ),
        UserChanges(
            username='fo/baz002',
            location_map={'abc123': 'def456'},
            unmapped_old_locations=[],
            unmapped_new_locations=[],
        ),
        UserChanges(
            username='fo/baz003',
            location_map={},
            unmapped_old_locations=['abc456'],
            unmapped_new_locations=[],
        ),
        UserChanges(
            username='fo/baz004',
            location_map={},
            unmapped_old_locations=[],
            unmapped_new_locations=['def789'],
        ),
    ]


def test_move_case_block_coro():
    move_case_block = move_case_block_coro('test-domain', dry_run=False)
    next(move_case_block)  # Prime the coroutine
    with patch('corehq.apps.users.management.commands.nphcda_move_users_cases.submit_case_blocks') as mock_submit:
        for i in range(CASE_BLOCK_COUNT + 1):
            move_case_block.send(f'case_block_{i}')

        assert mock_submit.call_count == 1
        assert len(mock_submit.call_args[0][0]) == CASE_BLOCK_COUNT

        move_case_block.close()

        assert mock_submit.call_count == 2
        assert mock_submit.call_args == call(
            ['case_block_1000'],
            'test-domain',
            device_id='corehq.apps.users.management.commands.nphcda_move_users_cases'
        )


def test_doctests():
    import corehq.apps.users.management.commands.nphcda_move_users_cases as module

    results = doctest.testmod(module)
    assert results.failed == 0
