import pytest
import sqlalchemy

from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.apps.project_db.populate import case_to_row_dict, upsert_case
from corehq.apps.project_db.schema import build_tables_for_domain
from corehq.apps.project_db.table_manager import create_tables, get_project_db_engine
from corehq.form_processor.models import CommCareCase

DOMAIN = 'test-full-stack'


@pytest.mark.django_db
class TestFullStack:
    """Happy-path test: data dictionary → schema → DDL → populate → query."""

    def setup_method(self):
        self.engine = get_project_db_engine()
        self._tables = []

    def teardown_method(self):
        for table in self._tables:
            table.drop(self.engine, checkfirst=True)

    def test_full_stack(self):
        # 1. Set up data dictionary
        dd_ct = CaseType.objects.create(domain=DOMAIN, name='patient')
        CaseProperty.objects.create(case_type=dd_ct, name='village', data_type='plain')
        CaseProperty.objects.create(case_type=dd_ct, name='dob', data_type='date')

        # 2. Build schema from data dictionary and create table
        metadata = sqlalchemy.MetaData()
        tables = build_tables_for_domain(metadata, DOMAIN)
        table = tables['patient']
        self._tables.append(table)
        create_tables(self.engine, metadata)

        # 3. Populate from a CommCareCase
        commcare_case = CommCareCase(
            case_id='case-001',
            owner_id='owner-1',
            name='Test Patient',
            opened_on='2025-01-15',
            modified_on='2025-06-01',
            server_modified_on='2025-06-01',
            case_json={'village': 'Brookfield', 'dob': '1990-05-20'},
        )

        row_dict = case_to_row_dict(commcare_case)
        upsert_case(self.engine, table, row_dict)

        # 4. Query and verify
        with self.engine.begin() as conn:
            result = conn.execute(
                table.select().where(table.c.case_id == 'case-001')
            )
            row = dict(result.fetchone())

        assert row['case_id'] == 'case-001'
        assert row['case_name'] == 'Test Patient'
        assert row['prop_village'] == 'Brookfield'
        assert row['prop_dob'] == '1990-05-20'
        assert row['prop_dob_date'] is not None
