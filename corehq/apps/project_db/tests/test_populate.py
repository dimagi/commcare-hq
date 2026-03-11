import datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest
import sqlalchemy

from corehq.apps.project_db.populate import (
    case_to_row_dict,
    coerce_to_date,
    coerce_to_number,
    upsert_case,
)
from corehq.apps.project_db.schema import build_table_for_case_type
from corehq.apps.project_db.table_manager import create_tables, get_project_db_engine

DOMAIN = 'test-populate'


@pytest.mark.django_db
class TestUpsertCase:

    def setup_method(self):
        self.engine = get_project_db_engine()
        self.metadata = sqlalchemy.MetaData()
        self.table = build_table_for_case_type(
            self.metadata, DOMAIN, 'patient',
            properties=[('first_name', 'plain')],
        )
        create_tables(self.engine, self.metadata)

    def teardown_method(self):
        with self.engine.begin() as conn:
            conn.execute(sqlalchemy.text(
                f'DROP TABLE IF EXISTS "{self.table.name}"'
            ))

    def _select_case(self, case_id):
        with self.engine.begin() as conn:
            result = conn.execute(
                self.table.select().where(self.table.c.case_id == case_id)
            )
            return dict(result.fetchone())

    def test_insert_new_case(self):
        case_data = {
            'case_id': 'case-001',
            'owner_id': 'owner-1',
            'case_name': 'Test Patient',
            'prop.first_name': 'Alice',
        }

        upsert_case(self.engine, self.table, case_data)

        row = self._select_case('case-001')
        assert row['case_id'] == 'case-001'
        assert row['owner_id'] == 'owner-1'
        assert row['case_name'] == 'Test Patient'
        assert row['prop__first_name'] == 'Alice'

    def test_upsert_updates_existing_case(self):
        case_data = {
            'case_id': 'case-002',
            'owner_id': 'owner-1',
            'case_name': 'Original Name',
            'prop.first_name': 'Bob',
        }
        upsert_case(self.engine, self.table, case_data)

        updated_data = {
            'case_id': 'case-002',
            'owner_id': 'owner-1',
            'case_name': 'Updated Name',
            'prop.first_name': 'Robert',
        }
        upsert_case(self.engine, self.table, updated_data)

        row = self._select_case('case-002')
        assert row['case_name'] == 'Updated Name'
        assert row['prop__first_name'] == 'Robert'

    def test_unknown_properties_are_ignored(self):
        case_data = {
            'case_id': 'case-004',
            'owner_id': 'owner-1',
            'prop.unknown_prop': 'should be skipped',
        }

        upsert_case(self.engine, self.table, case_data)

        row = self._select_case('case-004')
        assert row['case_id'] == 'case-004'


@pytest.mark.django_db
class TestUpsertCaseTypeCoercion:

    def setup_method(self):
        self.engine = get_project_db_engine()
        self.metadata = sqlalchemy.MetaData()
        self.table = build_table_for_case_type(
            self.metadata, DOMAIN, 'typed_patient',
            properties=[
                ('first_name', 'plain'),
                ('dob', 'date'),
                ('age', 'number'),
            ],
        )
        create_tables(self.engine, self.metadata)

    def teardown_method(self):
        with self.engine.begin() as conn:
            conn.execute(sqlalchemy.text(
                f'DROP TABLE IF EXISTS "{self.table.name}"'
            ))

    def _select_case(self, case_id):
        with self.engine.begin() as conn:
            result = conn.execute(
                self.table.select().where(self.table.c.case_id == case_id)
            )
            return dict(result.fetchone())

    def test_date_property_coerced(self):
        upsert_case(self.engine, self.table, {
            'case_id': 'tc-001',
            'owner_id': 'owner-1',
            'prop.dob': '1990-05-20',
        })

        row = self._select_case('tc-001')
        assert row['prop__dob'] == '1990-05-20'
        assert row['prop__dob__date'] == datetime.date(1990, 5, 20)

    def test_number_property_coerced(self):
        upsert_case(self.engine, self.table, {
            'case_id': 'tc-002',
            'owner_id': 'owner-1',
            'prop.age': '34',
        })

        row = self._select_case('tc-002')
        assert row['prop__age'] == '34'
        assert row['prop__age__numeric'] == Decimal('34')

    def test_invalid_date_sets_typed_column_to_none(self):
        upsert_case(self.engine, self.table, {
            'case_id': 'tc-003',
            'owner_id': 'owner-1',
            'prop.dob': 'not-a-date',
        })

        row = self._select_case('tc-003')
        assert row['prop__dob'] == 'not-a-date'
        assert row['prop__dob__date'] is None

    def test_invalid_number_sets_typed_column_to_none(self):
        upsert_case(self.engine, self.table, {
            'case_id': 'tc-004',
            'owner_id': 'owner-1',
            'prop.age': 'abc',
        })

        row = self._select_case('tc-004')
        assert row['prop__age'] == 'abc'
        assert row['prop__age__numeric'] is None

    def test_datetime_string_coerced_to_date(self):
        upsert_case(self.engine, self.table, {
            'case_id': 'tc-005',
            'owner_id': 'owner-1',
            'prop.dob': '1990-05-20T14:30:00',
        })

        row = self._select_case('tc-005')
        assert row['prop__dob__date'] == datetime.date(1990, 5, 20)


# --- Coercion unit tests (no DB needed) ---


class TestCoerceToDate:

    def test_iso_date(self):
        assert coerce_to_date('2024-03-15') == datetime.date(2024, 3, 15)

    def test_iso_datetime(self):
        assert coerce_to_date('2024-03-15T10:30:00') == datetime.date(2024, 3, 15)

    def test_none(self):
        assert coerce_to_date(None) is None

    def test_empty_string(self):
        assert coerce_to_date('') is None

    def test_invalid_string(self):
        assert coerce_to_date('not-a-date') is None

    def test_partial_date(self):
        assert coerce_to_date('2024-13-01') is None


class TestCoerceToNumber:

    def test_integer_string(self):
        assert coerce_to_number('42') == Decimal('42')

    def test_decimal_string(self):
        assert coerce_to_number('3.14') == Decimal('3.14')

    def test_negative(self):
        assert coerce_to_number('-7.5') == Decimal('-7.5')

    def test_none(self):
        assert coerce_to_number(None) is None

    def test_empty_string(self):
        assert coerce_to_number('') is None

    def test_invalid_string(self):
        assert coerce_to_number('abc') is None

    def test_whitespace(self):
        assert coerce_to_number('  ') is None


# --- Case adapter unit tests (no DB needed) ---


def _make_index(identifier, referenced_id):
    index = Mock()
    index.identifier = identifier
    index.referenced_id = referenced_id
    return index


def _make_case(case_json=None, live_indices=None, **fields):
    case = Mock()
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

    def test_parent_index_extracted(self):
        case = _make_case(live_indices=[
            _make_index('parent', 'parent-case-001'),
        ])
        result = case_to_row_dict(case)
        assert result['parent_id'] == 'parent-case-001'
        assert result['host_id'] is None

    def test_host_index_extracted(self):
        case = _make_case(live_indices=[
            _make_index('host', 'host-case-001'),
        ])
        result = case_to_row_dict(case)
        assert result['host_id'] == 'host-case-001'
        assert result['parent_id'] is None

    def test_both_indices_extracted(self):
        case = _make_case(live_indices=[
            _make_index('parent', 'parent-case-001'),
            _make_index('host', 'host-case-001'),
        ])
        result = case_to_row_dict(case)
        assert result['parent_id'] == 'parent-case-001'
        assert result['host_id'] == 'host-case-001'

    def test_no_indices_gives_none(self):
        case = _make_case()
        result = case_to_row_dict(case)
        assert result['parent_id'] is None
        assert result['host_id'] is None

    def test_non_standard_index_not_captured(self):
        case = _make_case(live_indices=[
            _make_index('custom_rel', 'other-case-001'),
        ])
        result = case_to_row_dict(case)
        assert result['parent_id'] is None
        assert result['host_id'] is None

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
