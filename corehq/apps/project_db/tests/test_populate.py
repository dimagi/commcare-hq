import datetime
from decimal import Decimal

import pytest
from unmagic import use

from corehq.apps.project_db.populate import (
    case_to_row,
    coerce_to_date,
    coerce_to_number,
    upsert_case,
)
from corehq.apps.project_db.table_ddl import CaseTable, get_project_db_engine
from corehq.form_processor.models import CommCareCase

from .util import project_db_table


@pytest.mark.parametrize('value, expected', [
    ('2024-03-15',          datetime.date(2024, 3, 15)),
    ('2024-03-15T10:30:00', datetime.date(2024, 3, 15)),
    (None,                  None),
    ('',                    None),
    ('not-a-date',          None),
    ('2024-13-01',          None),
])
def test_coerce_to_date(value, expected):
    assert coerce_to_date(value) == expected


@pytest.mark.parametrize('value, expected', [
    ('42',   Decimal('42')),
    ('3.14', Decimal('3.14')),
    ('-7.5', Decimal('-7.5')),
    (None,   None),
    ('',     None),
    ('abc',  None),
    ('  ',   None),
])
def test_coerce_to_number(value, expected):
    assert coerce_to_number(value) == expected


def _make_index(identifier, referenced_id):
    return {'identifier': identifier, 'referenced_id': referenced_id}


def _make_case(case_json=None, indices=None, **fields):
    return CommCareCase(
        case_id=fields.get('case_id', 'abc123'),
        domain=fields.get('domain', 'test-domain'),
        type=fields.get('type', 'patient'),
        name=fields.get('name', 'Test Case'),
        owner_id=fields.get('owner_id', 'owner1'),
        opened_on=fields.get('opened_on', datetime.datetime(2025, 1, 1)),
        closed_on=fields.get('closed_on', None),
        modified_on=fields.get('modified_on', datetime.datetime(2025, 6, 1)),
        closed=fields.get('closed', False),
        external_id=fields.get('external_id', ''),
        server_modified_on=fields.get('server_modified_on', datetime.datetime(2025, 6, 1)),
        case_json=case_json or {},
        indices=indices or [],
    )


def test_static_fields_mapped_to_columns():
    case = _make_case(
        case_id='abc123',
        owner_id='owner1',
        name='My Case',
        opened_on=datetime.datetime(2025, 1, 1),
        closed_on=datetime.datetime(2025, 3, 1),
        modified_on=datetime.datetime(2025, 6, 1),
        closed=True,
        external_id='ext-1',
        server_modified_on=datetime.datetime(2025, 6, 2),
        indices=[_make_index('parent', 'p1'), _make_index('host', 'h1')],
    )
    assert case_to_row(case, table_columns=set()) == {
        'case_id': 'abc123',
        'owner_id': 'owner1',
        'case_name': 'My Case',
        'opened_on': datetime.datetime(2025, 1, 1),
        'closed_on': datetime.datetime(2025, 3, 1),
        'modified_on': datetime.datetime(2025, 6, 1),
        'closed': True,
        'external_id': 'ext-1',
        'server_modified_on': datetime.datetime(2025, 6, 2),
        'parent_id': 'p1',
        'host_id': 'h1',
    }


@pytest.mark.parametrize('case_json, columns, expected_props', [
    # property dropped when it has no column
    ({'color': 'red', 'size': 'large'}, {'prop__color'}, {'prop__color': 'red'}),
    # raw value coerced to str
    ({'count': 42}, {'prop__count'}, {'prop__count': '42'}),
    # typed columns populated via coercion
    ({'dob': '1990-05-20', 'weight': '70.5'},
     {'prop__dob', 'prop__dob__date', 'prop__weight', 'prop__weight__number'},
     {'prop__dob': '1990-05-20', 'prop__dob__date': datetime.date(1990, 5, 20),
      'prop__weight': '70.5', 'prop__weight__number': Decimal('70.5')}),
    # typed value skipped when only the raw column exists
    ({'dob': '1990-05-20'}, {'prop__dob'}, {'prop__dob': '1990-05-20'}),
])
def test_property_columns(case_json, columns, expected_props):
    result = case_to_row(_make_case(case_json=case_json), columns)
    assert {k: v for k, v in result.items() if k.startswith('prop__')} == expected_props


@pytest.mark.parametrize('indices, expected_parent, expected_host', [
    ([],                             None, None),
    ([_make_index('parent', 'p1')],  'p1', None),
    ([_make_index('host',   'h1')],  None, 'h1'),
    ([_make_index('custom', 'x1')],  None, None),
])
def test_index_extraction(indices, expected_parent, expected_host):
    result = case_to_row(_make_case(indices=indices), table_columns=set())
    assert result['parent_id'] == expected_parent
    assert result['host_id'] == expected_host


def test_case_json_keys_cannot_collide_with_fixed_fields():
    case = _make_case(
        case_id='real-id',
        owner_id='real-owner',
        case_json={'case_id': 'fake-id', 'owner_id': 'fake-owner'},
    )
    result = case_to_row(case, table_columns={'prop__case_id', 'prop__owner_id'})
    assert result['case_id'] == 'real-id'
    assert result['owner_id'] == 'real-owner'
    # case_json values are namespaced under prop__, so they coexist safely
    assert result['prop__case_id'] == 'fake-id'
    assert result['prop__owner_id'] == 'fake-owner'


@use('db', project_db_table('test-upsert', 'patient', {'first_name': 'plain'}))
def test_upsert():
    table = CaseTable('test-upsert', 'patient').reflect()
    with get_project_db_engine().begin() as conn:
        upsert_case(conn, table, _make_case(case_id='c1', name='Alice'))
        rows = conn.execute(table.select()).fetchall()
        assert [row['case_id'] for row in rows] == ['c1']

        upsert_case(conn, table, _make_case(case_id='c1', name='Bob'))
        rows = conn.execute(table.select()).fetchall()
        assert len(rows) == 1  # updated in place, not inserted twice
        assert rows[0]['case_name'] == 'Bob'
