import datetime

import pytest
import sqlalchemy
from sqlalchemy import and_, func, select

from corehq.apps.project_db.populate import upsert_case
from corehq.apps.project_db.schema import build_table_for_case_type
from corehq.apps.project_db.table_manager import create_tables, get_project_db_engine

DOMAIN = 'test-queries'

HOUSEHOLDS = [
    {'case_id': 'hh-0', 'owner_id': 'owner-1', 'district': 'Kamuli', 'village': 'Village A'},
    {'case_id': 'hh-1', 'owner_id': 'owner-1', 'district': 'Kamuli', 'village': 'Village B'},
    {'case_id': 'hh-2', 'owner_id': 'owner-1', 'district': 'Jinja', 'village': 'Village C'},
]

PATIENTS = [
    {'case_id': 'pt-0', 'owner_id': 'owner-1', 'first_name': 'Alice', 'dob': '2020-01-15',
     'age': '5', 'indices': {'parent': 'hh-0'}},
    {'case_id': 'pt-1', 'owner_id': 'owner-1', 'first_name': 'Bob', 'dob': '2018-06-01',
     'age': '7', 'indices': {'parent': 'hh-0'}},
    {'case_id': 'pt-2', 'owner_id': 'owner-1', 'first_name': 'Carol', 'dob': '2022-03-10',
     'age': '3', 'indices': {'parent': 'hh-1'}},
    {'case_id': 'pt-3', 'owner_id': 'owner-1', 'first_name': 'Dan', 'dob': '2015-11-20',
     'age': '10', 'indices': {'parent': 'hh-2'}},
]


@pytest.mark.django_db
class TestCrossRelationshipQueries:

    def setup_method(self):
        self.engine = get_project_db_engine()
        self.metadata = sqlalchemy.MetaData()
        self.hh_table = build_table_for_case_type(
            self.metadata, DOMAIN, 'household',
            properties=[('district', 'plain'), ('village', 'plain')],
        )
        self.pt_table = build_table_for_case_type(
            self.metadata, DOMAIN, 'patient',
            properties=[
                ('first_name', 'plain'),
                ('dob', 'date'),
                ('age', 'number'),
            ],
            relationships=[('parent', 'household')],
        )
        create_tables(self.engine, self.metadata)

        for hh in HOUSEHOLDS:
            upsert_case(self.engine, self.hh_table, hh)
        for pt in PATIENTS:
            upsert_case(self.engine, self.pt_table, pt)

    def teardown_method(self):
        with self.engine.begin() as conn:
            conn.execute(sqlalchemy.text(
                f'DROP TABLE IF EXISTS "{self.pt_table.name}"'
            ))
            conn.execute(sqlalchemy.text(
                f'DROP TABLE IF EXISTS "{self.hh_table.name}"'
            ))

    def _join_condition(self):
        return self.pt_table.c.idx_parent == self.hh_table.c.case_id

    def test_join_patient_to_household(self):
        stmt = (
            select([self.pt_table.c.case_id, self.hh_table.c.prop_district])
            .select_from(
                self.pt_table.join(self.hh_table, self._join_condition())
            )
        )
        with self.engine.begin() as conn:
            rows = conn.execute(stmt).fetchall()

        assert len(rows) == 4
        assert all(row.prop_district is not None for row in rows)

    def test_filter_by_parent_property(self):
        stmt = (
            select([self.pt_table.c.prop_first_name])
            .select_from(
                self.pt_table.join(self.hh_table, self._join_condition())
            )
            .where(self.hh_table.c.prop_district == 'Kamuli')
            .order_by(self.pt_table.c.prop_first_name)
        )
        with self.engine.begin() as conn:
            rows = conn.execute(stmt).fetchall()

        names = [row.prop_first_name for row in rows]
        assert names == ['Alice', 'Bob', 'Carol']

    def test_filter_on_both_tables(self):
        stmt = (
            select([self.pt_table.c.prop_first_name])
            .select_from(
                self.pt_table.join(self.hh_table, self._join_condition())
            )
            .where(and_(
                self.hh_table.c.prop_district == 'Kamuli',
                self.pt_table.c.prop_dob_date > datetime.date(2019, 1, 1),
            ))
            .order_by(self.pt_table.c.prop_first_name)
        )
        with self.engine.begin() as conn:
            rows = conn.execute(stmt).fetchall()

        names = [row.prop_first_name for row in rows]
        assert names == ['Alice', 'Carol']

    def test_aggregate_by_parent(self):
        stmt = (
            select([
                self.hh_table.c.case_id,
                func.count(self.pt_table.c.case_id).label('patient_count'),
            ])
            .select_from(
                self.pt_table.join(self.hh_table, self._join_condition())
            )
            .group_by(self.hh_table.c.case_id)
            .order_by(self.hh_table.c.case_id)
        )
        with self.engine.begin() as conn:
            rows = conn.execute(stmt).fetchall()

        counts = {row.case_id: row.patient_count for row in rows}
        assert counts == {'hh-0': 2, 'hh-1': 1, 'hh-2': 1}
