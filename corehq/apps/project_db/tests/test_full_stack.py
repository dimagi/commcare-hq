import pytest
import sqlalchemy

from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.apps.project_db.populate import case_to_row_dict, upsert_case
from corehq.apps.project_db.schema import get_project_db_engine, sync_domain_tables
from corehq.form_processor.models import CommCareCase, CommCareCaseIndex

DOMAIN = 'test-full-stack'


@pytest.mark.django_db
class TestFullStack:
    """Happy-path test: data dictionary → schema → DDL → populate → query."""

    def setup_method(self):
        self.engine = get_project_db_engine()
        self._schemas = set()

    def teardown_method(self):
        with self.engine.begin() as conn:
            for schema in self._schemas:
                conn.execute(sqlalchemy.text(
                    f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'
                ))

    def test_full_stack(self):
        self._create_data_dictionary()
        tables = self._build_and_create_tables()
        self._populate_household(tables['household'])
        self._populate_patient(tables['patient'])
        self._verify_single_table_query(tables['patient'])
        self._verify_parent_join(tables['patient'], tables['household'])

    def _create_data_dictionary(self):
        dd_household = CaseType.objects.create(domain=DOMAIN, name='household')
        CaseProperty.objects.create(
            case_type=dd_household, name='district', data_type='plain',
        )
        dd_patient = CaseType.objects.create(domain=DOMAIN, name='patient')
        CaseProperty.objects.create(
            case_type=dd_patient, name='dob', data_type='date',
        )

    def _build_and_create_tables(self):
        tables = sync_domain_tables(self.engine, DOMAIN)
        self._schemas.update(t.schema for t in tables.values())
        return tables

    def _populate_household(self, table):
        household = CommCareCase(
            case_id='hh-001',
            owner_id='owner-1',
            name='The Smiths',
            modified_on='2025-06-01',
            server_modified_on='2025-06-01',
            case_json={'district': 'Kamuli'},
        )
        with self.engine.begin() as conn:
            upsert_case(conn, table, case_to_row_dict(household))

    def _populate_patient(self, table):
        patient = CommCareCase(
            case_id='pt-001',
            owner_id='owner-1',
            name='Alice Smith',
            modified_on='2025-06-01',
            server_modified_on='2025-06-01',
            case_json={'dob': '1990-05-20'},
        )
        patient.cached_indices = [
            CommCareCaseIndex(
                identifier='parent',
                referenced_id='hh-001',
                referenced_type='household',
                relationship_id=CommCareCaseIndex.CHILD,
            ),
        ]
        with self.engine.begin() as conn:
            upsert_case(conn, table, case_to_row_dict(patient))

    def _verify_single_table_query(self, patient_table):
        with self.engine.begin() as conn:
            row = dict(conn.execute(
                patient_table.select().where(
                    patient_table.c.case_id == 'pt-001',
                )
            ).fetchone())
        assert row['case_name'] == 'Alice Smith'
        assert row['prop__dob'] == '1990-05-20'
        assert row['prop__dob__date'] is not None
        assert row['parent_id'] == 'hh-001'

    def _verify_parent_join(self, patient_table, household_table):
        query = (
            sqlalchemy.select([patient_table.c.case_name])
            .select_from(patient_table.join(
                household_table,
                patient_table.c.parent_id == household_table.c.case_id,
            ))
            .where(household_table.c.prop__district == 'Kamuli')
        )
        with self.engine.begin() as conn:
            rows = conn.execute(query).fetchall()
        assert len(rows) == 1
        assert rows[0].case_name == 'Alice Smith'
