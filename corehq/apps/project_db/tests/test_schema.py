import pytest
import sqlalchemy
from sqlalchemy import Boolean, DateTime, Text

from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.apps.project_db.schema import (
    FIXED_COLUMNS,
    build_table_schema,
    build_all_table_schemas,
    get_case_table_schema,
    get_schema_name,
)


def test_get_schema_name():
    assert str(get_schema_name('my-domain')) == 'projectdb_my-domain'


# (name, sa_type, primary_key, nullable, has_timezone)
# has_timezone=None means don't assert on timezone (non-DateTime column).
FIXED_COLUMN_SPECS = [
    ('case_id',            Text,     True,  False, None),
    ('owner_id',           Text,     False, False, None),
    ('case_name',          Text,     False, True,  None),
    ('opened_on',          DateTime, False, True,  True),
    ('closed_on',          DateTime, False, True,  True),
    ('modified_on',        DateTime, False, True,  True),
    ('closed',             Boolean,  False, True,  None),
    ('external_id',        Text,     False, True,  None),
    ('server_modified_on', DateTime, False, True,  True),
    ('parent_id',          Text,     False, True,  None),
    ('host_id',            Text,     False, True,  None),
]


@pytest.mark.parametrize(
    'col_name, sa_type, primary_key, nullable, has_timezone',
    FIXED_COLUMN_SPECS,
    ids=[spec[0] for spec in FIXED_COLUMN_SPECS],
)
def test_fixed_column_definition(
    col_name, sa_type, primary_key, nullable, has_timezone,
):
    table = build_table_schema('d', 'person')
    col = table.c[col_name]
    assert isinstance(col.type, sa_type)
    assert col.primary_key is primary_key
    assert col.nullable is nullable
    if has_timezone is not None:
        assert col.type.timezone is has_timezone


def test_all_fixed_columns_present():
    table = build_table_schema('d', 'person')
    assert {c.name for c in table.columns} == {
        spec[0] for spec in FIXED_COLUMN_SPECS
    }


class TestBuildTableForCaseType:

    def setup_method(self):
        self.metadata = sqlalchemy.MetaData()
        self.table = build_table_schema(
            'test-domain', 'person', metadata=self.metadata,
        )

    def test_table_name_is_case_type(self):
        assert self.table.name == 'person'

    def test_table_schema_is_domain_schema(self):
        assert self.table.schema == get_schema_name('test-domain')

    def test_plain_property_adds_text_column(self):
        table = build_table_schema(
            'test-domain', 'household',
            properties=[('village', 'plain')],
        )
        col = table.c['prop__village']
        assert isinstance(col.type, sqlalchemy.Text)

    def test_plain_property_adds_one_column_only(self):
        table = build_table_schema(
            'test-domain', 'household2',
            properties=[('village', 'plain')],
        )
        column_names = {col.name for col in table.columns}
        assert column_names == {spec[0] for spec in FIXED_COLUMN_SPECS} | {'prop__village'}

    def test_date_property_adds_text_and_date_columns(self):
        table = build_table_schema(
            'test-domain', 'visit',
            properties=[('dob', 'date')],
        )
        assert isinstance(table.c['prop__dob'].type, sqlalchemy.Text)
        assert isinstance(table.c['prop__dob__date'].type, sqlalchemy.Date)

    def test_number_property_adds_text_and_numeric_columns(self):
        table = build_table_schema(
            'test-domain', 'visit2',
            properties=[('age', 'number')],
        )
        assert isinstance(table.c['prop__age'].type, sqlalchemy.Text)
        assert isinstance(table.c['prop__age__numeric'].type, sqlalchemy.Numeric)

    def test_select_property_adds_one_column_only(self):
        table = build_table_schema(
            'test-domain', 'visit3',
            properties=[('status', 'select')],
        )
        column_names = {col.name for col in table.columns}
        assert column_names == {spec[0] for spec in FIXED_COLUMN_SPECS} | {'prop__status'}

    def test_undefined_property_adds_one_column_only(self):
        table = build_table_schema(
            'test-domain', 'visit4',
            properties=[('misc', '')],
        )
        column_names = {col.name for col in table.columns}
        assert column_names == {spec[0] for spec in FIXED_COLUMN_SPECS} | {'prop__misc'}

    def test_multiple_properties_correct_column_count(self):
        table = build_table_schema(
            'test-domain', 'visit5',
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


SCHEMA_GEN_DOMAIN = 'test-schema-gen'


@pytest.mark.django_db
class TestBuildTablesForDomain:

    def test_returns_table_per_active_case_type(self):
        CaseType.objects.create(domain=SCHEMA_GEN_DOMAIN, name='person')
        CaseType.objects.create(domain=SCHEMA_GEN_DOMAIN, name='household')

        tables = build_all_table_schemas(SCHEMA_GEN_DOMAIN)

        assert set(tables.keys()) == {'person', 'household'}

    def test_empty_domain_returns_empty_dict(self):
        tables = build_all_table_schemas('empty-domain')

        assert tables == {}

    def test_deprecated_case_types_excluded(self):
        CaseType.objects.create(domain=SCHEMA_GEN_DOMAIN, name='active_type')
        CaseType.objects.create(
            domain=SCHEMA_GEN_DOMAIN, name='old_type', is_deprecated=True,
        )

        tables = build_all_table_schemas(SCHEMA_GEN_DOMAIN)

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

        tables = build_all_table_schemas(SCHEMA_GEN_DOMAIN)

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

        tables = build_all_table_schemas(SCHEMA_GEN_DOMAIN)

        table = tables['visit']
        column_names = {col.name for col in table.columns}
        assert 'prop__active_prop' in column_names
        assert 'prop__old_prop' not in column_names

    def test_does_not_include_other_domains(self):
        CaseType.objects.create(domain='other-domain', name='person')

        tables = build_all_table_schemas(SCHEMA_GEN_DOMAIN)

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

        table = build_table_schema(
            'test-domain', 'patient',
            properties=[('color', 'plain')],
        )
        self._schemas.append(table.schema)
        create_tables(self.engine, table.metadata)

        schema = get_case_table_schema('test-domain', 'patient')
        col_names = {c.name for c in schema.columns}
        assert 'prop__color' in col_names
