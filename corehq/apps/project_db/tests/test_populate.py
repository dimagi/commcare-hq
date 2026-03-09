import datetime
from decimal import Decimal

import pytest
import sqlalchemy

from corehq.apps.project_db.populate import upsert_case
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
            relationships=[('parent', 'household')],
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
            'first_name': 'Alice',
        }

        upsert_case(self.engine, self.table, case_data)

        row = self._select_case('case-001')
        assert row['case_id'] == 'case-001'
        assert row['owner_id'] == 'owner-1'
        assert row['case_name'] == 'Test Patient'
        assert row['prop_first_name'] == 'Alice'

    def test_upsert_updates_existing_case(self):
        case_data = {
            'case_id': 'case-002',
            'owner_id': 'owner-1',
            'case_name': 'Original Name',
            'first_name': 'Bob',
        }
        upsert_case(self.engine, self.table, case_data)

        updated_data = {
            'case_id': 'case-002',
            'owner_id': 'owner-1',
            'case_name': 'Updated Name',
            'first_name': 'Robert',
        }
        upsert_case(self.engine, self.table, updated_data)

        row = self._select_case('case-002')
        assert row['case_name'] == 'Updated Name'
        assert row['prop_first_name'] == 'Robert'

    def test_index_column_populated(self):
        case_data = {
            'case_id': 'case-003',
            'owner_id': 'owner-1',
            'indices': {'parent': 'hh-001'},
        }

        upsert_case(self.engine, self.table, case_data)

        row = self._select_case('case-003')
        assert row['idx_parent'] == 'hh-001'

    def test_unknown_properties_are_ignored(self):
        case_data = {
            'case_id': 'case-004',
            'owner_id': 'owner-1',
            'unknown_prop': 'should be skipped',
        }

        upsert_case(self.engine, self.table, case_data)

        row = self._select_case('case-004')
        assert row['case_id'] == 'case-004'

    def test_unknown_indices_are_ignored(self):
        case_data = {
            'case_id': 'case-005',
            'owner_id': 'owner-1',
            'indices': {'host': 'host-001'},
        }

        upsert_case(self.engine, self.table, case_data)

        row = self._select_case('case-005')
        assert row['case_id'] == 'case-005'


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
            relationships=[('parent', 'household')],
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
            'dob': '1990-05-20',
        })

        row = self._select_case('tc-001')
        assert row['prop_dob'] == '1990-05-20'
        assert row['prop_dob_date'] == datetime.date(1990, 5, 20)

    def test_number_property_coerced(self):
        upsert_case(self.engine, self.table, {
            'case_id': 'tc-002',
            'owner_id': 'owner-1',
            'age': '34',
        })

        row = self._select_case('tc-002')
        assert row['prop_age'] == '34'
        assert row['prop_age_numeric'] == Decimal('34')

    def test_invalid_date_sets_typed_column_to_none(self):
        upsert_case(self.engine, self.table, {
            'case_id': 'tc-003',
            'owner_id': 'owner-1',
            'dob': 'not-a-date',
        })

        row = self._select_case('tc-003')
        assert row['prop_dob'] == 'not-a-date'
        assert row['prop_dob_date'] is None

    def test_invalid_number_sets_typed_column_to_none(self):
        upsert_case(self.engine, self.table, {
            'case_id': 'tc-004',
            'owner_id': 'owner-1',
            'age': 'abc',
        })

        row = self._select_case('tc-004')
        assert row['prop_age'] == 'abc'
        assert row['prop_age_numeric'] is None

    def test_datetime_string_coerced_to_date(self):
        upsert_case(self.engine, self.table, {
            'case_id': 'tc-005',
            'owner_id': 'owner-1',
            'dob': '1990-05-20T14:30:00',
        })

        row = self._select_case('tc-005')
        assert row['prop_dob_date'] == datetime.date(1990, 5, 20)
