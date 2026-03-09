import sqlalchemy

from corehq.apps.project_db.schema import (
    build_table_for_case_type,
    get_project_db_table_name,
)

FIXED_COLUMNS = {
    'case_id': (sqlalchemy.Text, True),   # (type, is_primary_key)
    'owner_id': (sqlalchemy.Text, False),
    'case_name': (sqlalchemy.Text, False),
    'opened_on': (sqlalchemy.DateTime, False),
    'closed_on': (sqlalchemy.DateTime, False),
    'modified_on': (sqlalchemy.DateTime, False),
    'closed': (sqlalchemy.Boolean, False),
    'external_id': (sqlalchemy.Text, False),
    'server_modified_on': (sqlalchemy.DateTime, False),
}


class TestGetProjectDbTableName:

    def test_starts_with_prefix(self):
        name = get_project_db_table_name('test-domain', 'person')
        assert name.startswith('projectdb_')

    def test_contains_domain_and_case_type(self):
        name = get_project_db_table_name('my-domain', 'household')
        assert 'my-domain' in name
        assert 'household' in name

    def test_within_postgres_limit(self):
        name = get_project_db_table_name(
            'a-very-long-domain-name-that-keeps-going',
            'a-very-long-case-type-name-that-also-keeps-going',
        )
        assert len(name) <= 63

    def test_deterministic(self):
        name1 = get_project_db_table_name('domain', 'case_type')
        name2 = get_project_db_table_name('domain', 'case_type')
        assert name1 == name2

    def test_different_domains_produce_different_names(self):
        name1 = get_project_db_table_name('domain-a', 'person')
        name2 = get_project_db_table_name('domain-b', 'person')
        assert name1 != name2

    def test_different_case_types_produce_different_names(self):
        name1 = get_project_db_table_name('domain', 'person')
        name2 = get_project_db_table_name('domain', 'household')
        assert name1 != name2


class TestBuildTableForCaseType:

    def setup_method(self):
        self.metadata = sqlalchemy.MetaData()
        self.table = build_table_for_case_type(
            self.metadata, 'test-domain', 'person',
        )

    def test_table_name_starts_with_prefix(self):
        assert self.table.name.startswith('projectdb_')

    def test_has_all_fixed_columns(self):
        column_names = {col.name for col in self.table.columns}
        assert column_names == set(FIXED_COLUMNS)

    def test_column_types(self):
        for col_name, (expected_type, _) in FIXED_COLUMNS.items():
            col = self.table.c[col_name]
            assert isinstance(col.type, expected_type), (
                f"Column {col_name}: expected {expected_type}, "
                f"got {type(col.type)}"
            )

    def test_case_id_is_primary_key(self):
        pk_columns = [col.name for col in self.table.primary_key.columns]
        assert pk_columns == ['case_id']

    def test_owner_id_is_not_nullable(self):
        assert self.table.c.owner_id.nullable is False

    def test_datetime_columns_have_timezone(self):
        datetime_columns = [
            'opened_on', 'closed_on', 'modified_on', 'server_modified_on',
        ]
        for col_name in datetime_columns:
            col = self.table.c[col_name]
            assert col.type.timezone is True, (
                f"Column {col_name} should have timezone=True"
            )

    def test_accepts_unused_properties_param(self):
        table = build_table_for_case_type(
            self.metadata, 'test-domain', 'household',
            properties=[{'name': 'age', 'type': 'number'}],
        )
        # For now, properties are ignored; table has only fixed columns
        assert {col.name for col in table.columns} == set(FIXED_COLUMNS)

    def test_accepts_unused_relationships_param(self):
        table = build_table_for_case_type(
            self.metadata, 'test-domain', 'visit',
            relationships=[{'case_type': 'person', 'identifier': 'parent'}],
        )
        assert {col.name for col in table.columns} == set(FIXED_COLUMNS)
