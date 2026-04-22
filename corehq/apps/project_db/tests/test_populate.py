import datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest
import sqlalchemy

from corehq.apps.project_db.populate import (
    case_to_row_dict,
    coerce_to_date,
    coerce_to_number,
    send_to_project_db,
    upsert_case,
)
from corehq.apps.project_db.schema import build_table_schema
from corehq.apps.project_db.schema import create_tables, get_project_db_engine

DOMAIN = 'test-populate'


@pytest.mark.django_db
class TestUpsertCase:

    def setup_method(self):
        self.engine = get_project_db_engine()
        self.table = build_table_schema(
            DOMAIN, 'patient',
            properties=[
                ('first_name', 'plain'),
                ('dob', 'date'),
            ],
        )
        create_tables(self.engine, self.table.metadata)

    def teardown_method(self):
        with self.engine.begin() as conn:
            conn.execute(sqlalchemy.text(
                f'DROP SCHEMA IF EXISTS "{self.table.schema}" CASCADE'
            ))

    def _upsert(self, case_data):
        with self.engine.begin() as conn:
            upsert_case(conn, self.table, case_data)

    def _select_case(self, case_id):
        with self.engine.begin() as conn:
            result = conn.execute(
                self.table.select().where(self.table.c.case_id == case_id)
            )
            return dict(result.fetchone())

    def test_insert_new_case(self):
        self._upsert({
            'case_id': 'case-001',
            'owner_id': 'owner-1',
            'case_name': 'Test Patient',
            'prop.first_name': 'Alice',
        })

        row = self._select_case('case-001')
        assert row['case_id'] == 'case-001'
        assert row['owner_id'] == 'owner-1'
        assert row['case_name'] == 'Test Patient'
        assert row['prop__first_name'] == 'Alice'

    def test_upsert_updates_existing_case(self):
        self._upsert({
            'case_id': 'case-002', 'owner_id': 'o',
            'case_name': 'Original', 'prop.first_name': 'Bob',
        })
        self._upsert({
            'case_id': 'case-002', 'owner_id': 'o',
            'case_name': 'Updated', 'prop.first_name': 'Robert',
        })

        row = self._select_case('case-002')
        assert row['case_name'] == 'Updated'
        assert row['prop__first_name'] == 'Robert'

    def test_typed_column_round_trip(self):
        """Smoke test that typed columns are populated via coercion. Unit tests
        for coerce_to_date / coerce_to_number cover the edge cases — this test
        only verifies the DB write path is wired up."""
        self._upsert({
            'case_id': 'case-003', 'owner_id': 'o',
            'prop.dob': '1990-05-20',
        })

        row = self._select_case('case-003')
        assert row['prop__dob'] == '1990-05-20'
        assert row['prop__dob__date'] == datetime.date(1990, 5, 20)

    def test_unknown_properties_are_ignored(self):
        self._upsert({
            'case_id': 'case-unknown',
            'owner_id': 'owner-1',
            'prop.not_a_real_property': 'should be skipped',
        })

        row = self._select_case('case-unknown')
        assert row['case_id'] == 'case-unknown'


# --- Coercion unit tests (no DB needed) ---


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


# --- Case adapter unit tests (no DB needed) ---


def _make_index(identifier, referenced_id):
    index = Mock()
    index.identifier = identifier
    index.referenced_id = referenced_id
    return index


def _make_case(case_json=None, live_indices=None, **fields):
    case = Mock()
    case.type = fields.get('type', 'default')
    case.case_id = fields.get('case_id', 'abc123')
    case.owner_id = fields.get('owner_id', 'owner1')
    case.name = fields.get('name', 'Test Case')
    case.opened_on = fields.get('opened_on', '2025-01-01')
    case.closed_on = fields.get('closed_on', None)
    case.modified_on = fields.get('modified_on', '2025-06-01')
    case.closed = fields.get('closed', False)
    case.external_id = fields.get('external_id', '')
    case.server_modified_on = fields.get('server_modified_on', '2025-06-01')
    case.case_json = case_json or {}
    case.live_indices = live_indices or []
    return case


class TestCaseToRowDict:

    def test_fixed_fields_extracted(self):
        case = _make_case(
            case_id='abc123',
            owner_id='owner1',
            name='My Case',
            opened_on='2025-01-01',
            closed_on='2025-03-01',
            modified_on='2025-06-01',
            closed=True,
            external_id='ext-1',
            server_modified_on='2025-06-02',
        )
        result = case_to_row_dict(case)

        assert result['case_id'] == 'abc123'
        assert result['owner_id'] == 'owner1'
        assert result['case_name'] == 'My Case'
        assert result['opened_on'] == '2025-01-01'
        assert result['closed_on'] == '2025-03-01'
        assert result['modified_on'] == '2025-06-01'
        assert result['closed'] is True
        assert result['external_id'] == 'ext-1'
        assert result['server_modified_on'] == '2025-06-02'

    def test_dynamic_properties_from_case_json(self):
        case = _make_case(case_json={'color': 'red', 'size': 'large'})
        result = case_to_row_dict(case)

        assert result['prop.color'] == 'red'
        assert result['prop.size'] == 'large'

    def test_empty_case_json_no_extra_keys(self):
        case = _make_case(case_json={})
        result = case_to_row_dict(case)

        expected_keys = {
            'case_id', 'owner_id', 'case_name', 'opened_on', 'closed_on',
            'modified_on', 'closed', 'external_id', 'server_modified_on',
            'parent_id', 'host_id',
        }
        assert set(result.keys()) == expected_keys

    @pytest.mark.parametrize('indices, expected_parent, expected_host', [
        ([],                                                    None, None),
        ([_make_index('parent', 'p1')],                         'p1', None),
        ([_make_index('host',   'h1')],                         None, 'h1'),
        ([_make_index('parent', 'p1'),
          _make_index('host',   'h1')],                         'p1', 'h1'),
        ([_make_index('custom', 'x1')],                         None, None),
    ])
    def test_index_extraction(self, indices, expected_parent, expected_host):
        case = _make_case(live_indices=indices)
        result = case_to_row_dict(case)
        assert result['parent_id'] == expected_parent
        assert result['host_id'] == expected_host

    def test_case_json_keys_cannot_collide_with_fixed_fields(self):
        """The prop. prefix ensures case_json keys never collide with
        fixed fields."""
        case = _make_case(
            case_id='real-id',
            owner_id='real-owner',
            case_json={
                'case_id': 'fake-id',
                'owner_id': 'fake-owner',
            },
        )
        result = case_to_row_dict(case)

        assert result['case_id'] == 'real-id'
        assert result['owner_id'] == 'real-owner'
        # The case_json values are namespaced, so they coexist safely
        assert result['prop.case_id'] == 'fake-id'
        assert result['prop.owner_id'] == 'fake-owner'


# --- send_to_project_db tests (requires DB) ---


SEND_DOMAIN = 'test-send-to-project-db'


@pytest.mark.django_db
class TestSendToProjectDb:

    def setup_method(self):
        self.engine = get_project_db_engine()
        metadata = sqlalchemy.MetaData()
        self.patient_table = build_table_schema(
            SEND_DOMAIN, 'patient', metadata=metadata,
            properties=[('first_name', 'plain')],
        )
        self.household_table = build_table_schema(
            SEND_DOMAIN, 'household', metadata=metadata,
            properties=[('district', 'plain')],
        )
        create_tables(self.engine, metadata)

    def teardown_method(self):
        schema = self.patient_table.schema
        with self.engine.begin() as conn:
            conn.execute(sqlalchemy.text(
                f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'
            ))

    def _select_all(self, table):
        with self.engine.begin() as conn:
            rows = conn.execute(table.select()).fetchall()
            return [dict(row) for row in rows]

    def test_single_case_type(self):
        cases = [
            _make_case(type='patient', case_id='pt-1', owner_id='o1',
                       case_json={'first_name': 'Alice'}),
        ]
        send_to_project_db(SEND_DOMAIN, cases)

        rows = self._select_all(self.patient_table)
        assert len(rows) == 1
        assert rows[0]['case_id'] == 'pt-1'
        assert rows[0]['prop__first_name'] == 'Alice'

    def test_multiple_case_types(self):
        cases = [
            _make_case(type='patient', case_id='pt-1', owner_id='o1',
                       case_json={'first_name': 'Alice'}),
            _make_case(type='household', case_id='hh-1', owner_id='o1',
                       case_json={'district': 'Kamuli'}),
        ]
        send_to_project_db(SEND_DOMAIN, cases)

        patients = self._select_all(self.patient_table)
        households = self._select_all(self.household_table)
        assert len(patients) == 1
        assert len(households) == 1
        assert patients[0]['prop__first_name'] == 'Alice'
        assert households[0]['prop__district'] == 'Kamuli'

    def test_unknown_case_type_skipped(self):
        cases = [
            _make_case(type='patient', case_id='pt-1', owner_id='o1'),
            _make_case(type='unknown_type', case_id='u-1', owner_id='o1'),
        ]
        send_to_project_db(SEND_DOMAIN, cases)

        patients = self._select_all(self.patient_table)
        assert len(patients) == 1

    def test_all_unknown_case_types_is_noop(self):
        send_to_project_db(SEND_DOMAIN, [
            _make_case(type='unknown_type', case_id='u-1', owner_id='o1'),
        ])
        # No error raised, no rows written
        assert self._select_all(self.patient_table) == []

    def test_empty_cases_is_noop(self):
        send_to_project_db(SEND_DOMAIN, [])
        assert self._select_all(self.patient_table) == []

    def test_multiple_cases_same_type(self):
        cases = [
            _make_case(type='patient', case_id='pt-1', owner_id='o1',
                       case_json={'first_name': 'Alice'}),
            _make_case(type='patient', case_id='pt-2', owner_id='o1',
                       case_json={'first_name': 'Bob'}),
        ]
        send_to_project_db(SEND_DOMAIN, cases)

        rows = self._select_all(self.patient_table)
        assert len(rows) == 2
        names = {r['prop__first_name'] for r in rows}
        assert names == {'Alice', 'Bob'}
