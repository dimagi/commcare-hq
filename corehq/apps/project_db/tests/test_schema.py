import pytest
import sqlalchemy
from sqlalchemy import Boolean, DateTime, Text
from sqlalchemy import inspect as sa_inspect

from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.apps.project_db.schema import (
    build_all_table_schemas,
    build_table_schema,
    create_tables,
    evolve_table,
    get_case_table_schema,
    get_project_db_engine,
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


@pytest.mark.parametrize(
    'column', ['owner_id', 'modified_on', 'parent_id', 'host_id'],
)
def test_indexed_column(column):
    table = build_table_schema('d', 'person')
    assert f'ix_person_{column}' in {idx.name for idx in table.indexes}


def test_table_name_is_case_type():
    table = build_table_schema('test-domain', 'person')
    assert table.name == 'person'


def test_table_schema_is_domain_schema():
    table = build_table_schema('test-domain', 'person')
    assert table.schema == get_schema_name('test-domain')


@pytest.mark.parametrize(
    'data_type, extra_columns',
    [
        ('plain',  {'prop__x'}),
        ('select', {'prop__x'}),
        ('',       {'prop__x'}),
        ('date',   {'prop__x', 'prop__x__date'}),
        ('number', {'prop__x', 'prop__x__numeric'}),
    ],
)
def test_property_adds_expected_columns(data_type, extra_columns):
    table = build_table_schema('d', 't', properties=[('x', data_type)])
    fixed = {spec[0] for spec in FIXED_COLUMN_SPECS}
    assert {c.name for c in table.columns} - fixed == extra_columns


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


DDL_DOMAIN = 'test-ddl-ops'


def _table_exists(engine, table_name, schema):
    return table_name in sa_inspect(engine).get_table_names(schema=schema)


def _table_columns(engine, table_name, schema):
    return {
        c['name']
        for c in sa_inspect(engine).get_columns(table_name, schema=schema)
    }


def _table_indexes(engine, table_name, schema):
    return {
        idx['name']
        for idx in sa_inspect(engine).get_indexes(table_name, schema=schema)
    }


@pytest.mark.django_db
class TestDDLOperations:
    """Exercises create_tables, evolve_table, and get_case_table_schema against
    a live PostgreSQL connection. Each test uses a distinct case type so they
    can share one schema; the schema is dropped in teardown.
    """

    def setup_method(self):
        self.engine = get_project_db_engine()
        self.schema = get_schema_name(DDL_DOMAIN)

    def teardown_method(self):
        with self.engine.begin() as conn:
            conn.execute(sqlalchemy.text(
                f'DROP SCHEMA IF EXISTS "{self.schema}" CASCADE'
            ))

    def _create(self, case_type, properties=None):
        """Build a table and create it in the DB. Returns the SQLAlchemy Table."""
        table = build_table_schema(
            DDL_DOMAIN, case_type,
            metadata=sqlalchemy.MetaData(),
            properties=properties or [],
        )
        create_tables(self.engine, table.metadata)
        return table

    def test_create_table(self):
        table = self._create('create_simple', [('name', 'plain')])
        assert _table_exists(self.engine, table.name, table.schema)

    def test_create_is_idempotent(self):
        table = self._create('create_idempotent', [('name', 'plain')])
        create_tables(self.engine, table.metadata)  # second time
        assert _table_exists(self.engine, table.name, table.schema)

    def test_evolve_adds_new_column(self):
        self._create('evolve_add_col', [('name', 'plain')])
        table2 = build_table_schema(
            DDL_DOMAIN, 'evolve_add_col',
            properties=[('name', 'plain'), ('age', 'number')],
        )

        evolve_table(self.engine, table2)

        columns = _table_columns(self.engine, table2.name, table2.schema)
        assert 'prop__age' in columns
        assert 'prop__age__numeric' in columns

    def test_evolve_adds_new_index(self):
        self._create('evolve_add_idx', [('name', 'plain')])
        table2 = build_table_schema(
            DDL_DOMAIN, 'evolve_add_idx',
            properties=[('name', 'plain')],
        )
        sqlalchemy.Index(f'ix_{table2.name}_case_name', table2.c['case_name'])

        evolve_table(self.engine, table2)

        indexes = _table_indexes(self.engine, table2.name, table2.schema)
        assert f'ix_{table2.name}_case_name' in indexes

    def test_evolve_does_not_drop_columns(self):
        self._create(
            'evolve_no_drop',
            [('name', 'plain'), ('village', 'plain')],
        )
        table2 = build_table_schema(
            DDL_DOMAIN, 'evolve_no_drop',
            properties=[('name', 'plain')],
        )

        evolve_table(self.engine, table2)

        columns = _table_columns(self.engine, table2.name, table2.schema)
        assert 'prop__village' in columns

    def test_reflect_returns_none_for_missing_table(self):
        assert get_case_table_schema(DDL_DOMAIN, 'reflect_missing') is None

    def test_reflect_live_schema(self):
        self._create('reflect_live', [('color', 'plain')])

        reflected = get_case_table_schema(DDL_DOMAIN, 'reflect_live')
        assert 'prop__color' in {c.name for c in reflected.columns}
