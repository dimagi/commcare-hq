import pytest
import sqlalchemy

from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.apps.project_db.populate import send_to_project_db
from corehq.apps.project_db.schema import (
    get_project_db_engine,
    sync_domain_tables,
)
from corehq.form_processor.models import CommCareCase, CommCareCaseIndex

DOMAIN = 'test-full-stack'


@pytest.mark.django_db
class TestFullStack:
    """Happy-path test: data dictionary -> schema -> DDL -> populate -> query.

    Enters via send_to_project_db (the public API) so this test also covers
    case-type dispatch and unknown-type skipping.
    """

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
        self._populate(tables)
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

    def _populate(self, tables):
        household = CommCareCase(
            case_id='hh-001',
            type='household',
            owner_id='owner-1',
            name='The Smiths',
            modified_on='2025-06-01',
            server_modified_on='2025-06-01',
            case_json={'district': 'Kamuli'},
        )
        patient = CommCareCase(
            case_id='pt-001',
            type='patient',
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
        # Include an unknown case type to exercise the dispatch-skip path.
        stranger = CommCareCase(
            case_id='stranger-001',
            owner_id='owner-1',
            name='Unknown',
            modified_on='2025-06-01',
            server_modified_on='2025-06-01',
            case_json={},
        )
        stranger.type = 'not_in_dictionary'

        send_to_project_db(DOMAIN, [household, patient, stranger])

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
