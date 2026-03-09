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

    def test_plain_property_adds_text_column(self):
        table = build_table_for_case_type(
            self.metadata, 'test-domain', 'household',
            properties=[('village', 'plain')],
        )
        col = table.c['prop_village']
        assert isinstance(col.type, sqlalchemy.Text)

    def test_plain_property_adds_one_column_only(self):
        table = build_table_for_case_type(
            self.metadata, 'test-domain', 'household2',
            properties=[('village', 'plain')],
        )
        column_names = {col.name for col in table.columns}
        assert column_names == set(FIXED_COLUMNS) | {'prop_village'}

    def test_date_property_adds_text_and_date_columns(self):
        table = build_table_for_case_type(
            self.metadata, 'test-domain', 'visit',
            properties=[('dob', 'date')],
        )
        assert isinstance(table.c['prop_dob'].type, sqlalchemy.Text)
        assert isinstance(table.c['prop_dob_date'].type, sqlalchemy.Date)

    def test_number_property_adds_text_and_numeric_columns(self):
        table = build_table_for_case_type(
            self.metadata, 'test-domain', 'visit2',
            properties=[('age', 'number')],
        )
        assert isinstance(table.c['prop_age'].type, sqlalchemy.Text)
        assert isinstance(table.c['prop_age_numeric'].type, sqlalchemy.Numeric)

    def test_select_property_adds_one_column_only(self):
        table = build_table_for_case_type(
            self.metadata, 'test-domain', 'visit3',
            properties=[('status', 'select')],
        )
        column_names = {col.name for col in table.columns}
        assert column_names == set(FIXED_COLUMNS) | {'prop_status'}

    def test_undefined_property_adds_one_column_only(self):
        table = build_table_for_case_type(
            self.metadata, 'test-domain', 'visit4',
            properties=[('misc', '')],
        )
        column_names = {col.name for col in table.columns}
        assert column_names == set(FIXED_COLUMNS) | {'prop_misc'}

    def test_multiple_properties_correct_column_count(self):
        table = build_table_for_case_type(
            self.metadata, 'test-domain', 'visit5',
            properties=[
                ('village', 'plain'),
                ('dob', 'date'),
                ('age', 'number'),
                ('status', 'select'),
            ],
        )
        # 9 fixed + 4 raw text + 1 date + 1 numeric = 15
        assert len(table.columns) == 15
