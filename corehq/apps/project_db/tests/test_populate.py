import datetime
import uuid
from decimal import Decimal
from unittest.mock import patch

import pytest
import sqlalchemy
from sqlalchemy import func
from unmagic import use

from corehq.apps.project_db.populate import (
    backfill_typed_columns,
    case_to_row,
    populate_case_type,
    send_cases_to_project_db,
    upsert_cases,
)
from corehq.apps.project_db.table_ddl import (
    CaseTable,
    get_project_db_engine,
    truncate_identifier,
)
from corehq.form_processor.models import CommCareCase
from corehq.util.metrics.tests.utils import capture_metrics

from .util import project_db_table


to_date = func.lib_projectdb.coerce_to_date
to_number = func.lib_projectdb.coerce_to_number
to_array = func.lib_projectdb.coerce_to_array
to_gps = func.lib_projectdb.coerce_to_gps


@pytest.mark.parametrize('coercion, expected', [
    (to_date('2024-03-15'), datetime.date(2024, 3, 15)),
    (to_date('2024-03-15T10:30:00'), datetime.date(2024, 3, 15)),
    (to_date(None), None),
    (to_date(''), None),
    (to_date('2024-02-30'), None),
    (to_date('15/03/2024'), None),
    (to_number('-7.5'), Decimal('-7.5')),
    (to_number(None), None),
    (to_number(''), None),
    (to_number('abc'), None),
    (to_number(' 42 '), Decimal('42')),
    (to_number('1e3'), Decimal('1E+3')),
    (to_number('1_000'), None),
    (to_number('1e1000000'), None),
    (to_array(' red '), ['red']),
    (to_array('red  blue'), ['red', 'blue']),
    (to_array(None), []),
    (to_array(''), []),
    (to_array('  '), []),
    (func.latitude(to_gps('42.365 -71.102')), pytest.approx(42.365)),
    (func.longitude(to_gps('42.365 -71.102')), pytest.approx(-71.102)),
    (func.latitude(to_gps('42.365 -71.102 x')), pytest.approx(42.365)),  # extra values ignored
    (to_gps(None), None),
    (to_gps(''), None),
    (to_gps('0'), None),
    (to_gps('0  0'), None),  # double space makes an empty element
    (to_gps('91 0'), None),
    (to_gps('0 181'), None),
    (to_gps('NaN 0'), None),
])
@use('db')
def test_sql_coercion(coercion, expected):
    with get_project_db_engine().begin() as conn:
        result = conn.execute(sqlalchemy.select([coercion])).scalar()
    assert result == expected


def _make_index(identifier, referenced_id):
    return {'identifier': identifier, 'referenced_id': referenced_id}


def _make_case(case_json=None, indices=None, **fields):
    return CommCareCase(
        case_id=fields.get('case_id', str(uuid.uuid4())),
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
    assert case_to_row(case, columns=[]) == {
        'case_id': 'abc123',
        'owner_id': 'owner1',
        'case_name': 'My Case',
        'opened_on': _utc_datetime(2025, 1, 1),
        'closed_on': _utc_datetime(2025, 3, 1),
        'modified_on': _utc_datetime(2025, 6, 1),
        'closed': True,
        'external_id': 'ext-1',
        'server_modified_on': _utc_datetime(2025, 6, 2),
        'parent_id': 'p1',
        'host_id': 'h1',
    }


def _utc_datetime(*args):
    return datetime.datetime(*args, tzinfo=datetime.timezone.utc)


def _property_columns(properties):
    """The columns CaseTable builds for ``{name: data_type}``"""
    with patch.object(CaseTable, '_get_dd_properties', return_value=properties.items()):
        return list(CaseTable('domain', 'case_type')._build_property_columns())


@pytest.mark.parametrize('case_json, properties, expected_props', [
    # property dropped when it has no column
    ({'color': 'red', 'size': 'large'}, {'color': 'plain'}, {'prop__color': 'red'}),
    # raw value coerced to str
    ({'count': 42}, {'count': 'plain'}, {'prop__count': '42'}),
    # missing or None values become empty strings
    ({}, {'color': 'plain'}, {'prop__color': ''}),
    ({'color': None}, {'color': 'plain'}, {'prop__color': ''}),
    # truncated column names are matched by their comment
    ({'x' * 100: 'long'}, {'x' * 100: 'plain'},
     {truncate_identifier('prop__' + 'x' * 100): 'long'}),
    # typed columns coerced in SQL are left to upsert_cases
    ({'dob': '1990-05-20', 'weight': '70.5', 'interests': 'sports music'},
     {'dob': 'date', 'weight': 'number', 'interests': 'select'},
     {'prop__dob': '1990-05-20', 'prop__weight': '70.5',
      'prop__interests': 'sports music'}),
])
def test_property_columns(case_json, properties, expected_props):
    columns = _property_columns(properties)
    result = case_to_row(_make_case(case_json=case_json), columns)
    assert {k: v for k, v in result.items() if 'prop__' in k} == expected_props


@pytest.mark.parametrize('indices, expected_parent, expected_host', [
    ([],                             None, None),
    ([_make_index('parent', 'p1')],  'p1', None),
    ([_make_index('host',   'h1')],  None, 'h1'),
    ([_make_index('custom', 'x1')],  None, None),
])
def test_index_extraction(indices, expected_parent, expected_host):
    result = case_to_row(_make_case(indices=indices), columns=[])
    assert result['parent_id'] == expected_parent
    assert result['host_id'] == expected_host


def test_case_json_keys_cannot_collide_with_fixed_fields():
    case = _make_case(
        case_id='real-id',
        owner_id='real-owner',
        case_json={'case_id': 'fake-id', 'owner_id': 'fake-owner'},
    )
    columns = _property_columns({'case_id': 'plain', 'owner_id': 'plain'})
    result = case_to_row(case, columns)
    assert result['case_id'] == 'real-id'
    assert result['owner_id'] == 'real-owner'
    # case_json values are namespaced under prop__, so they coexist safely
    assert result['prop__case_id'] == 'fake-id'
    assert result['prop__owner_id'] == 'fake-owner'


@use('db', project_db_table('test-upsert', 'patient', {'first_name': 'plain'}))
def test_upsert():
    table = CaseTable('test-upsert', 'patient').reflect()
    with get_project_db_engine().begin() as conn:
        upsert_cases(conn, table, [_make_case(case_id='c1', name='Alice')])
        rows = conn.execute(table.select()).fetchall()
        assert [row['case_id'] for row in rows] == ['c1']

        upsert_cases(conn, table, [_make_case(case_id='c1', name='Bob')])
        rows = conn.execute(table.select()).fetchall()
        assert len(rows) == 1  # updated in place, not inserted twice
        assert rows[0]['case_name'] == 'Bob'


@use('db', project_db_table('test-send', 'patient', {'first_name': 'plain'}))
def test_populate_case_type():
    populate_case_type('test-send', 'patient', [
        _make_case({'first_name': 'Alice'}, type='patient'),
        _make_case({'first_name': 'Bob'}, type='patient'),
        _make_case({}, type='patient'),
    ])

    table = CaseTable('test-send', 'patient').reflect()
    with get_project_db_engine().begin() as conn:
        rows = conn.execute(table.select()).fetchall()
    assert [r[0] for r in rows] == ['Alice', 'Bob', '']
    assert CaseTable('test-upsert', 'clinic').reflect() is None


@use('db', project_db_table('test-typed', 'patient', {
    'dob': 'date', 'weight': 'number', 'interests': 'select', 'location': 'gps',
}))
def test_send_typed_properties_round_trip():
    populate_case_type('test-typed', 'patient', [
        _make_case({
            'dob': '1990-05-20',
            'weight': '70.5',
            'interests': 'sports music',
            'location': '42.365 -71.102',
        }, type='patient'),
    ])

    table = CaseTable('test-typed', 'patient').reflect()
    with get_project_db_engine().begin() as conn:
        row = conn.execute(sqlalchemy.select([
            table.c.date_prop__dob,
            table.c.number_prop__weight,
            table.c.select_prop__interests,
            func.latitude(table.c.gps_prop__location),
        ])).fetchone()
    assert tuple(row) == (
        datetime.date(1990, 5, 20),
        Decimal('70.5'),
        ['sports', 'music'],
        pytest.approx(42.365),
    )


@use('db', project_db_table('test-long-prop', 'patient', {'x' * 100: 'date'}))
def test_send_long_property_name_round_trip():
    # A property whose column name exceeds Postgres's 63-byte limit must survive
    # create -> reflect -> upsert with the DDL and populate sides agreeing.
    long_name = 'x' * 100
    populate_case_type('test-long-prop', 'patient', [
        _make_case({long_name: '1990-05-20'}, type='patient'),
    ])

    table = CaseTable('test-long-prop', 'patient').reflect()
    plain_col = truncate_identifier(f'prop__{long_name}')
    typed_col = truncate_identifier(f'date_prop__{long_name}')
    with get_project_db_engine().begin() as conn:
        rows = conn.execute(table.select()).fetchall()
    assert rows[0][plain_col] == '1990-05-20'
    assert rows[0][typed_col] == datetime.date(1990, 5, 20)


@use('db', project_db_table('test-send', 'patient', {'first_name': 'plain'}))
def test_populate_case_type_bad_type():
    with pytest.raises(ValueError):
        populate_case_type('test-send', 'patient', [
            _make_case({'first_name': 'Alice'}, type='patient'),
            _make_case({'first_name': 'Bob'}, type='patient'),
            _make_case({}, type='clinic'),
        ])


@use('db')
def test_send_cases_to_project_db():
    domain = 'test-mixed'
    with project_db_table(domain, 'patient', {'first_name': 'plain'}), \
         project_db_table(domain, 'clinic', {'city': 'plain'}), \
         capture_metrics() as metrics:
        send_cases_to_project_db(domain, [
            _make_case({'first_name': 'Alice'}, case_id='c1', type='patient'),
            _make_case({'city': 'Boston'}, case_id='c2', type='clinic'),
            _make_case({'first_name': 'Bob'}, case_id='c3', type='patient'),
            _make_case({}, case_id='c4', type='no-such-table'),  # skipped
        ])
        with get_project_db_engine().begin() as conn:
            patients = conn.execute(CaseTable(domain, 'patient').reflect().select()).fetchall()
            clinics = conn.execute(CaseTable(domain, 'clinic').reflect().select()).fetchall()

    assert sorted(r['case_id'] for r in patients) == ['c1', 'c3']
    assert [r['case_id'] for r in clinics] == ['c2']
    assert metrics.list('commcare.project_db.populate.duration', domain=domain), metrics


def test_missing_external_id_is_empty_string():
    case = _make_case(external_id=None)
    assert case_to_row(case, columns=[])['external_id'] == ''


@use('db', project_db_table('test-backfill', 'patient', {'dob': 'date', 'weight': 'number'}, (
    ['case_id', 'owner_id', 'prop__dob', 'prop__weight'], [
        ('a', 'o', '2020-01-01', '12'),
        ('b', 'o', '2021-02-02', ''),
        ('c', 'o', 'not a date', '3.5'),
        ('d', 'o', '2022-03-03', 'heavy'),
        ('e', 'o', '', '7'),
    ])))
def test_backfill_typed_columns():
    # A plain insert skips the SQL coercion, leaving the typed columns NULL
    table = CaseTable('test-backfill', 'patient').reflect()
    backfill_typed_columns(
        table, [table.c.date_prop__dob, table.c.number_prop__weight], chunk_size=2)

    with get_project_db_engine().begin() as conn:
        rows = conn.execute(sqlalchemy.select([
            table.c.case_id, table.c.date_prop__dob, table.c.number_prop__weight,
        ]))
        values = {case_id: (dob, weight) for case_id, dob, weight in rows}
    assert values == {
        'a': (datetime.date(2020, 1, 1), Decimal('12')),
        'b': (datetime.date(2021, 2, 2), None),
        'c': (None, Decimal('3.5')),
        'd': (datetime.date(2022, 3, 3), None),
        'e': (None, Decimal('7')),
    }
