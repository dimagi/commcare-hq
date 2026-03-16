import pytest
import sqlalchemy

from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.apps.project_db.schema import (
    FIXED_COLUMNS,
    build_table_for_case_type,
    build_tables_for_domain,
    get_case_table_schema,
    get_schema_name,
)

# Derive test expectations from the canonical FIXED_COLUMNS definition.
# Maps column name to (expected_sqlalchemy_type, is_primary_key).
# FIXED_COLUMNS entries mix classes (Text) and instances (DateTime(timezone=True)),
# so we normalize: classes pass through, instances yield their type.
FIXED_COLUMN_EXPECTATIONS = {
    name: (col_type if isinstance(col_type, type) else type(col_type),
           kwargs.get('primary_key', False))
    for name, col_type, kwargs in FIXED_COLUMNS
}


class TestGetSchemaName:

    def test_starts_with_prefix(self):
        assert get_schema_name('test-domain').startswith('projectdb_')

    def test_contains_domain(self):
        assert 'my-domain' in get_schema_name('my-domain')

    def test_deterministic(self):
        assert get_schema_name('domain') == get_schema_name('domain')

    def test_different_domains_produce_different_names(self):
        assert get_schema_name('domain-a') != get_schema_name('domain-b')


class TestBuildTableForCaseType:

    def setup_method(self):
        self.metadata = sqlalchemy.MetaData()
        self.table = build_table_for_case_type(
            self.metadata, 'test-domain', 'person',
        )

    def test_table_name_is_case_type(self):
        assert self.table.name == 'person'

    def test_table_schema_is_domain_schema(self):
        assert self.table.schema == get_schema_name('test-domain')

    def test_has_all_fixed_columns(self):
        column_names = {col.name for col in self.table.columns}
        assert column_names == set(FIXED_COLUMN_EXPECTATIONS)

    def test_column_types(self):
        for col_name, (expected_type, _) in FIXED_COLUMN_EXPECTATIONS.items():
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
        col = table.c['prop__village']
        assert isinstance(col.type, sqlalchemy.Text)

    def test_plain_property_adds_one_column_only(self):
        table = build_table_for_case_type(
            self.metadata, 'test-domain', 'household2',
            properties=[('village', 'plain')],
        )
        column_names = {col.name for col in table.columns}
        assert column_names == set(FIXED_COLUMN_EXPECTATIONS) | {'prop__village'}

    def test_date_property_adds_text_and_date_columns(self):
        table = build_table_for_case_type(
            self.metadata, 'test-domain', 'visit',
            properties=[('dob', 'date')],
        )
        assert isinstance(table.c['prop__dob'].type, sqlalchemy.Text)
        assert isinstance(table.c['prop__dob__date'].type, sqlalchemy.Date)

    def test_number_property_adds_text_and_numeric_columns(self):
        table = build_table_for_case_type(
            self.metadata, 'test-domain', 'visit2',
            properties=[('age', 'number')],
        )
        assert isinstance(table.c['prop__age'].type, sqlalchemy.Text)
        assert isinstance(table.c['prop__age__numeric'].type, sqlalchemy.Numeric)

    def test_select_property_adds_one_column_only(self):
        table = build_table_for_case_type(
            self.metadata, 'test-domain', 'visit3',
            properties=[('status', 'select')],
        )
        column_names = {col.name for col in table.columns}
        assert column_names == set(FIXED_COLUMN_EXPECTATIONS) | {'prop__status'}

    def test_undefined_property_adds_one_column_only(self):
        table = build_table_for_case_type(
            self.metadata, 'test-domain', 'visit4',
            properties=[('misc', '')],
        )
        column_names = {col.name for col in table.columns}
        assert column_names == set(FIXED_COLUMN_EXPECTATIONS) | {'prop__misc'}

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
        # fixed + 4 raw text + 1 date + 1 numeric
        assert len(table.columns) == len(FIXED_COLUMNS) + 6

    def test_owner_id_has_index(self):
        index_names = {idx.name for idx in self.table.indexes}
        assert 'ix_person_owner_id' in index_names

    def test_modified_on_has_index(self):
        index_names = {idx.name for idx in self.table.indexes}
        assert 'ix_person_modified_on' in index_names

    def test_parent_id_has_index(self):
        index_names = {idx.name for idx in self.table.indexes}
        assert 'ix_person_parent_id' in index_names

    def test_host_id_has_index(self):
        index_names = {idx.name for idx in self.table.indexes}
        assert 'ix_person_host_id' in index_names

    def test_parent_id_is_nullable(self):
        assert self.table.c.parent_id.nullable is True

    def test_host_id_is_nullable(self):
        assert self.table.c.host_id.nullable is True


SCHEMA_GEN_DOMAIN = 'test-schema-gen'


@pytest.mark.django_db
class TestBuildTablesForDomain:

    def test_returns_table_per_active_case_type(self):
        CaseType.objects.create(domain=SCHEMA_GEN_DOMAIN, name='person')
        CaseType.objects.create(domain=SCHEMA_GEN_DOMAIN, name='household')

        metadata = sqlalchemy.MetaData()
        tables = build_tables_for_domain(metadata, SCHEMA_GEN_DOMAIN)

        assert set(tables.keys()) == {'person', 'household'}

    def test_empty_domain_returns_empty_dict(self):
        metadata = sqlalchemy.MetaData()
        tables = build_tables_for_domain(metadata, 'empty-domain')

        assert tables == {}

    def test_deprecated_case_types_excluded(self):
        CaseType.objects.create(domain=SCHEMA_GEN_DOMAIN, name='active_type')
        CaseType.objects.create(
            domain=SCHEMA_GEN_DOMAIN, name='old_type', is_deprecated=True,
        )

        metadata = sqlalchemy.MetaData()
        tables = build_tables_for_domain(metadata, SCHEMA_GEN_DOMAIN)

        assert 'active_type' in tables
        assert 'old_type' not in tables

    def test_properties_become_columns(self):
        ct = CaseType.objects.create(domain=SCHEMA_GEN_DOMAIN, name='patient')
        CaseProperty.objects.create(
            case_type=ct, name='village', data_type='plain',
        )
        CaseProperty.objects.create(
            case_type=ct, name='dob', data_type='date',
        )

        metadata = sqlalchemy.MetaData()
        tables = build_tables_for_domain(metadata, SCHEMA_GEN_DOMAIN)

        table = tables['patient']
        column_names = {col.name for col in table.columns}
        assert 'prop__village' in column_names
        assert 'prop__dob' in column_names
        assert 'prop__dob__date' in column_names

    def test_deprecated_properties_excluded(self):
        ct = CaseType.objects.create(domain=SCHEMA_GEN_DOMAIN, name='visit')
        CaseProperty.objects.create(
            case_type=ct, name='active_prop', data_type='plain',
        )
        CaseProperty.objects.create(
            case_type=ct, name='old_prop', data_type='plain',
            deprecated=True,
        )

        metadata = sqlalchemy.MetaData()
        tables = build_tables_for_domain(metadata, SCHEMA_GEN_DOMAIN)

        table = tables['visit']
        column_names = {col.name for col in table.columns}
        assert 'prop__active_prop' in column_names
        assert 'prop__old_prop' not in column_names

    def test_does_not_include_other_domains(self):
        CaseType.objects.create(domain='other-domain', name='person')

        metadata = sqlalchemy.MetaData()
        tables = build_tables_for_domain(metadata, SCHEMA_GEN_DOMAIN)

        assert 'person' not in tables


@pytest.mark.django_db
class TestGetCaseTableSchema:

    def setup_method(self):
        from corehq.apps.project_db.schema import get_project_db_engine
        self.engine = get_project_db_engine()
        self._schemas = []

    def teardown_method(self):
        with self.engine.begin() as conn:
            for schema in self._schemas:
                conn.execute(sqlalchemy.text(
                    f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'
                ))

    def test_returns_none_when_table_does_not_exist(self):
        result = get_case_table_schema('test-domain', 'nonexistent')
        assert result is None

    def test_reflects_live_schema(self):
        from corehq.apps.project_db.schema import create_tables

        metadata = sqlalchemy.MetaData()
        table = build_table_for_case_type(
            metadata, 'test-domain', 'patient',
            properties=[('color', 'plain')],
        )
        self._schemas.append(table.schema)
        create_tables(self.engine, metadata)

        schema = get_case_table_schema('test-domain', 'patient')
        col_names = {c.name for c in schema.columns}
        assert 'prop__color' in col_names
