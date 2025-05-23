import doctest
import tempfile
from contextlib import contextmanager
from inspect import cleandoc
from typing import Iterator
from unittest.mock import call, patch

import pytest

from corehq.apps.locations.tests.util import LocationHierarchyPerTest
from corehq.apps.users.management.commands.nphcda_move_locations import (
    LocationError,
    Settlement,
    SettlementPair,
    load_csv,
    submit_case_block_coro,
)

DOMAIN = 'test-domain'


def test_load_csv():
    csv_content = cleandoc("""
        Username,Map from old location,,,,,Map to new location,,,,,Unmapped old locations,,,,,Unmapped new locations,,,,
        ,Scotland,Midlothian,Edinburgh,Craigleith,abc123,Scotland,Midlothian,Edinburgh,Inverleith,,,,,,,,,,,
        ,,,,,,,,,,,,,,,,,,,,
        """) + '\n'
    with get_temp_filename(csv_content) as csv_filename:
        location_pairs = list(load_csv(DOMAIN, csv_filename))
    assert location_pairs == [
        SettlementPair(
            old_settlement=Settlement(
                domain=DOMAIN,
                state_name='Scotland',
                lga_name='Midlothian',
                ward_name='Edinburgh',
                settlement_name='Craigleith',
                location_id='abc123',
            ),
            new_settlement=Settlement(
                domain=DOMAIN,
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
        chunk_size = 10
        with submit_case_block_coro(
            chunk_size,
            'test-domain',
            username='foo@bar.baz'
        ) as submit_case_block:
            for i in range(chunk_size + 1):
                submit_case_block.send(f'case_block_{i}')

            assert mock_submit.call_count == 1
            assert len(mock_submit.call_args[0][0]) == chunk_size

        assert mock_submit.call_count == 2
        assert mock_submit.call_args == call(
            [f'case_block_{chunk_size}'],
            'test-domain',
            username='foo@bar.baz'
        )


class TestSettlement(LocationHierarchyPerTest):
    domain = DOMAIN
    location_type_names = ['country', 'state', 'lga', 'ward', 'settlement']
    location_structure = [
        ('United Kingdom', [
            ('Scotland', [
                ('Midlothian', [
                    ('Edinburgh', [
                        ('New Town', []),
                    ]),
                ]),
            ]),
        ])
    ]

    def setUp(self):
        super().setUp()
        self.country = self.locations['United Kingdom']
        self.state = self.locations['Scotland']
        self.lga = self.locations['Midlothian']
        self.ward = self.locations['Edinburgh']
        self.settlement = self.locations['New Town']

    def test_get_state_code(self):
        settlement = Settlement(
            domain=DOMAIN,
            state_name='Scotland',
            lga_name='Midlothian',
            ward_name='Edinburgh',
            settlement_name='New Town',
            location_id=self.settlement.location_id,
        )
        assert settlement.get_state_code() == 'scotland'

    def test_get_lga_code(self):
        settlement = Settlement(
            domain=DOMAIN,
            state_name='Scotland',
            lga_name='Midlothian',
            ward_name='Edinburgh',
            settlement_name='New Town',
            location_id=self.settlement.location_id,
        )
        assert settlement.get_lga_code() == 'scotland·midlothian'

    def test_get_ward_code(self):
        settlement = Settlement(
            domain=DOMAIN,
            state_name='Scotland',
            lga_name='Midlothian',
            ward_name='Edinburgh',
            settlement_name='New Town',
            location_id=self.settlement.location_id,
        )
        assert settlement.get_ward_code() == 'scotland·midlothian·edinburgh'

    def test_get_settlement_code(self):
        settlement = Settlement(
            domain=DOMAIN,
            state_name='Scotland',
            lga_name='Midlothian',
            ward_name='Edinburgh',
            settlement_name='New Town',
            location_id=self.settlement.location_id,
        )
        assert settlement.get_settlement_code() == 'scotland·midlothian·edinburgh·new town'

    def test_get_site_code(self):
        settlement = Settlement(
            domain=DOMAIN,
            state_name='Scotland',
            lga_name='Midlothian',
            ward_name='Edinburgh',
            settlement_name='New Town',
            location_id=self.settlement.location_id,
        )
        assert settlement.get_site_code() == 'new_town_edinburgh_midlothian_scotland_settlement'

    def test_get_location(self):
        with patch(
            'corehq.apps.users.management.commands.nphcda_move_locations'
            '.COUNTRY_ID',
            self.country.location_id,
        ):
            settlement = Settlement(
                domain=DOMAIN,
                state_name='Scotland',
                lga_name='Midlothian',
                ward_name='Edinburgh',
                settlement_name='New Town',
                location_id=None,
            )

            location = settlement.get_location()
            assert location == self.settlement

    def test_get_location_settlement_not_found(self):
        with patch(
            'corehq.apps.users.management.commands.nphcda_move_locations'
            '.COUNTRY_ID',
            self.country.location_id,
        ):
            settlement = Settlement(
                domain=DOMAIN,
                state_name='Scotland',
                lga_name='Midlothian',
                ward_name='Edinburgh',
                settlement_name='West End',
                location_id=None,
            )

            with pytest.raises(LocationError, match=(
                "^No location found for 'West end' under Edinburgh "
                r"\([a-f0-9]{32}\)$"
            )):
                settlement.get_location()


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
