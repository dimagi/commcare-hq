import time

import pytest
import sqlalchemy
from sqlalchemy import and_, func, select

from corehq.apps.project_db.populate import upsert_case
from corehq.apps.project_db.schema import build_table_for_case_type
from corehq.apps.project_db.table_manager import create_tables, get_project_db_engine

DOMAIN = 'test-performance'

DISTRICTS = ['Kamuli', 'Jinja', 'Iganga', 'Bugiri', 'Mayuge']

HOUSEHOLD_PROPERTIES = [
    ('district', 'plain'),
    ('village', 'plain'),
    ('head_of_household', 'plain'),
]

PATIENT_PROPERTIES = [
    ('first_name', 'plain'),
    ('last_name', 'plain'),
    ('dob', 'date'),
    ('age', 'number'),
    ('sex', 'select'),
    ('phone', 'phone_number'),
    ('risk_level', 'select'),
]


def _make_household(i):
    district = DISTRICTS[i % len(DISTRICTS)]
    return {
        'case_id': f'hh-{i}',
        'owner_id': 'owner-1',
        'district': district,
        'village': f'Village-{i}',
        'head_of_household': f'Head-{i}',
    }


def _make_patient(i, household_count):
    hh_index = i % household_count
    return {
        'case_id': f'pt-{i}',
        'owner_id': 'owner-1',
        'first_name': f'First-{i}',
        'last_name': f'Last-{i}',
        'dob': f'20{(i % 25):02d}-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}',
        'age': str(i % 80),
        'sex': 'male' if i % 2 == 0 else 'female',
        'phone': f'+2567{i:07d}',
        'risk_level': ['low', 'medium', 'high'][i % 3],
        'indices': {'parent': f'hh-{hh_index}'},
    }


@pytest.mark.slow
@pytest.mark.django_db
class TestBulkInsert:

    def setup_method(self):
        self.engine = get_project_db_engine()
        self.metadata = sqlalchemy.MetaData()
        self.pt_table = build_table_for_case_type(
            self.metadata, DOMAIN, 'patient_bulk',
            properties=PATIENT_PROPERTIES,
            relationships=[('parent', 'household')],
        )
        create_tables(self.engine, self.metadata)

    def teardown_method(self):
        with self.engine.begin() as conn:
            conn.execute(sqlalchemy.text(
                f'DROP TABLE IF EXISTS "{self.pt_table.name}"'
            ))

    def test_insert_10k_cases(self):
        start = time.time()
        for i in range(10_000):
            upsert_case(self.engine, self.pt_table, _make_patient(i, 1000))
        elapsed = time.time() - start

        with self.engine.begin() as conn:
            count = conn.execute(
                select([func.count()]).select_from(self.pt_table)
            ).scalar()

        print(f"\nInserted 10,000 cases in {elapsed:.2f}s")
        assert count == 10_000


@pytest.mark.slow
@pytest.mark.django_db
class TestJoinQueryPerformance:

    def setup_method(self):
        self.engine = get_project_db_engine()
        self.metadata = sqlalchemy.MetaData()
        self.hh_table = build_table_for_case_type(
            self.metadata, DOMAIN, 'household_perf',
            properties=HOUSEHOLD_PROPERTIES,
        )
        self.pt_table = build_table_for_case_type(
            self.metadata, DOMAIN, 'patient_perf',
            properties=PATIENT_PROPERTIES,
            relationships=[('parent', 'household')],
        )
        create_tables(self.engine, self.metadata)
        self._populate_data()

    def teardown_method(self):
        with self.engine.begin() as conn:
            conn.execute(sqlalchemy.text(
                f'DROP TABLE IF EXISTS "{self.pt_table.name}"'
            ))
            conn.execute(sqlalchemy.text(
                f'DROP TABLE IF EXISTS "{self.hh_table.name}"'
            ))

    def _populate_data(self):
        for i in range(1_000):
            upsert_case(self.engine, self.hh_table, _make_household(i))
        for i in range(10_000):
            upsert_case(self.engine, self.pt_table, _make_patient(i, 1000))

    def _join_condition(self):
        return self.pt_table.c.idx_parent == self.hh_table.c.case_id

    def test_join_query_time(self):
        stmt = (
            select([self.pt_table.c.case_id, self.hh_table.c.prop_district])
            .select_from(
                self.pt_table.join(self.hh_table, self._join_condition())
            )
            .where(self.hh_table.c.prop_district == 'Kamuli')
        )

        start = time.time()
        with self.engine.begin() as conn:
            rows = conn.execute(stmt).fetchall()
        elapsed = time.time() - start

        # Kamuli is 1 of 5 districts, so ~2000 patients
        print(f"\nJOIN + filter returned {len(rows)} rows in {elapsed:.4f}s")
        assert len(rows) == 2_000

    def test_filtered_join_with_typed_column(self):
        stmt = (
            select([self.pt_table.c.case_id])
            .select_from(
                self.pt_table.join(self.hh_table, self._join_condition())
            )
            .where(and_(
                self.hh_table.c.prop_district == 'Kamuli',
                self.pt_table.c.prop_dob_date > '2010-01-01',
            ))
        )

        start = time.time()
        with self.engine.begin() as conn:
            rows = conn.execute(stmt).fetchall()
        elapsed = time.time() - start

        print(f"\nJOIN + district + dob filter returned {len(rows)} rows in {elapsed:.4f}s")
        assert len(rows) > 0
