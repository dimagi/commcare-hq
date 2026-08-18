from unittest.mock import patch

import pytest
import sqlalchemy
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from sqlalchemy import Table
from unmagic import fixture, use

from corehq.apps.project_db.table_ddl import (
    CaseTable,
    DomainSchema,
    Earth,
    create_or_update_project_db,
    get_domain_query_engine,
    get_project_db_engine,
    preview_drop,
    truncate_identifier,
    update_table,
)
from corehq.sql_db.connections import (
    PROJECT_DB_ENGINE_ID,
    ConnectionManager,
    connection_manager,
)

from .util import project_db_table


# DEBUG/UNIT_TESTING off so the dev/test fallback doesn't supply project_db
@override_settings(REPORTING_DATABASES={'default': 'default'}, DEBUG=False, UNIT_TESTING=False)
def test_get_project_db_engine_not_configured():
    with patch('corehq.apps.project_db.table_ddl.connection_manager', ConnectionManager()):
        with pytest.raises(ImproperlyConfigured, match='project_db'):
            get_project_db_engine()


def test_schema_name():
    assert DomainSchema('my-domain').name == 'projectdb_my-domain'


def test_schema_name_truncation():
    long_domain = 'd' * 100
    schema = DomainSchema(long_domain)
    assert schema.name == f'projectdb_{"d" * 44}_954c9921'
    assert len(schema.name.encode('utf-8')) <= 63


@pytest.mark.parametrize('identifier, expected', [
    ('prop__short', 'prop__short'),  # unchanged
    ('p' * 63, 'p' * 63),  # exactly at the limit
    ('p' * 64, 'p' * 54 + '_153ac90a'),  # over the limit
    ('prop__how_many_pecks_of_pickled_peppers_did_peter_piper_pick__a_peck',
     'prop__how_many_pecks_of_pickled_peppers_did_peter_pipe_aebfc91f'),
    ('prop__how_many_pecks_of_pickled_peppers_did_peter_piper_pick__enough',  # Same prefix as above
     'prop__how_many_pecks_of_pickled_peppers_did_peter_pipe_6e49f8dc'),
    ("A son dotà ‘d sust e ‘d consiensa e a dëvo agì j’un con j’àutri ant n’ëspìrit ëd fradlansa",
     "A son dotà ‘d sust e ‘d consiensa e a dëvo agì _47f54a51"),  # multi-byte chars > shorter result
])
def test_truncate_identifier(identifier, expected):
    assert len(expected.encode('utf-8')) <= 63
    assert truncate_identifier(identifier) == expected


@pytest.mark.parametrize('domain, expected', [
    ('mydomain', 'projectdb_mydomain'),
    ('my-domain', '"projectdb_my-domain"'),
    ('my"domain', '"projectdb_my""domain"'),
])
def test_quoted_name(domain, expected):
    assert DomainSchema(domain)._quoted_name == expected


@use('db')
def test_schema_lifecycle():
    engine = get_project_db_engine()
    schema = DomainSchema('test_schema_lifecycle')
    with engine.begin() as conn:
        schema.create(conn)
        assert schema.name in sqlalchemy.inspect(conn).get_schema_names()
        assert _role_exists(conn, schema)

        schema.create(conn)  # a second sync leaves both in place
        assert _role_exists(conn, schema)

        schema.drop(conn)
        assert schema.name not in sqlalchemy.inspect(conn).get_schema_names()
        assert not _role_exists(conn, schema)

        schema.drop(conn)  # dropping an absent schema and role is a no-op


def _role_exists(conn, schema):
    return bool(conn.execute(
        sqlalchemy.text('SELECT 1 FROM pg_roles WHERE rolname = :name'),
        {'name': schema.role_name},
    ).scalar())


@use('db')
def test_set_local_search_path():
    schema = DomainSchema('projectdbtestsearchpath')
    with get_project_db_engine().begin() as conn:
        schema.create(conn)
        schema.set_local_search_path(conn)
        search_path = conn.execute(sqlalchemy.text('SHOW search_path')).scalar()
        schema.drop(conn)
    assert search_path == schema.name

@use('db')
def test_long_domain_schema_lifecycle():
    # A domain whose schema name exceeds Postgres's 63-byte limit round-trips
    # through create -> lookup -> drop under its truncated name.
    engine = get_project_db_engine()
    schema = DomainSchema('d' * 100)
    with engine.begin() as conn:
        schema.create(conn)
        try:
            assert schema.name in sqlalchemy.inspect(conn).get_schema_names()
            assert schema.get_comment(conn) == 'd' * 100
            assert _role_exists(conn, schema)
        finally:
            schema.drop(conn)
        assert schema.name not in sqlalchemy.inspect(conn).get_schema_names()
        assert not _role_exists(conn, schema)


@override_settings(SECRET_KEY='thisismysecretkey')
@pytest.mark.parametrize('domain, expected', [
    ('my-domain', 'e656f61aff26f54fdf0037e3f120b38c2683437a2cd0efbb0fb21116eb34fcce'),
    ('my-other-domain', 'f70d9db254cab3b9e057e330b3d72b0d80fa69e24a062f20028539c225828d84'),
    ('long' * 100, '87ac4e25583ac8a98685d123011c339578e7d2f98a7c5fc8a9840f24e0e08489'),
    ('long' * 101, 'be0558082b24015ee9bca36c014615c7fe8190784fdc2b56b90cdaf50ba42c87'),
])
def test_role_password(domain, expected):
    assert DomainSchema(domain)._get_password() == expected


@use('db', project_db_table('projectdbtest-grants', 'patient', {'nickname': 'plain'}))
def test_role_is_granted_read_only_access():
    schema = DomainSchema('projectdbtest-grants')
    with get_project_db_engine().begin() as conn:
        # Schema privileges
        assert _has_schema_privilege(conn, schema.role_name, schema.name, 'USAGE')
        assert not _has_schema_privilege(conn, schema.role_name, schema.name, 'CREATE')

        # Table privileges
        assert _has_table_privilege(conn, schema, 'patient', 'SELECT')
        for privilege in ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER'):
            assert not _has_table_privilege(conn, schema, 'patient', privilege)


@use('db', project_db_table('projectdbtest-public', 'patient', {'nickname': 'plain'}))
def test_role_cannot_create_in_the_public_schema():
    schema = DomainSchema('projectdbtest-public')
    with get_project_db_engine().begin() as conn:
        assert _has_schema_privilege(conn, schema.role_name, 'public', 'USAGE')
        assert not _has_schema_privilege(conn, schema.role_name, 'public', 'CREATE')

@use('db', project_db_table('projectdbtest-new-table', 'patient', {'nickname': 'plain'}))
def test_a_later_sync_grants_read_on_a_new_table():
    # GRANT ON ALL TABLES is evaluated as the grant is made, so a table created
    # by a later sync is only readable because the grants are re-run
    domain = 'projectdbtest-new-table'
    with patch('corehq.apps.project_db.table_ddl._get_case_types',
               return_value=['patient', 'household']), \
         patch.object(CaseTable, '_get_dd_properties', return_value=[]):
        create_or_update_project_db(domain)

    schema = DomainSchema(domain)
    with get_project_db_engine().begin() as conn:
        assert _has_table_privilege(conn, schema, 'household', 'SELECT')


def _has_schema_privilege(conn, role, target, privilege):
    return _has_privilege(conn, 'has_schema_privilege', role, target, privilege)


def _has_table_privilege(conn, schema, table, privilege):
    target = f'{schema._quoted_name}.{table}'
    return _has_privilege(conn, 'has_table_privilege', schema.role_name, target, privilege)


def _has_privilege(conn, function, role, target, privilege):
    return conn.execute(
        sqlalchemy.text(f'SELECT {function}(:role, :target, :privilege)'),
        {'role': role, 'target': target, 'privilege': privilege},
    ).scalar()


@use('db', project_db_table('projectdbtest-mine', 'patient', {'nickname': 'plain'}),
     project_db_table('projectdbtest-yours', 'patient', {'nickname': 'plain'}))
def test_domain_query_engine_reads_only_its_own_schema():
    mine = DomainSchema('projectdbtest-mine')
    yours = DomainSchema('projectdbtest-yours')
    engine = get_domain_query_engine('projectdbtest-mine')
    with engine.connect() as conn:
        assert conn.execute(sqlalchemy.text('SELECT current_user')).scalar() == mine.role_name

        count = conn.execute(sqlalchemy.text(
            f'SELECT count(*) FROM {mine._quoted_name}.patient'
        )).scalar()
        assert count == 0

        # Fail when attempting to access another schema
        with pytest.raises(sqlalchemy.exc.ProgrammingError, match='permission denied'):
            conn.execute(sqlalchemy.text(
                f'SELECT count(*) FROM {yours._quoted_name}.patient'
            ))


@use('db', project_db_table('projectdbtest-readonly', 'patient', {'nickname': 'plain'}))
def test_domain_query_engine_cannot_write():
    schema = DomainSchema('projectdbtest-readonly')
    engine = get_domain_query_engine('projectdbtest-readonly')
    with engine.connect() as conn:
        with pytest.raises(sqlalchemy.exc.ProgrammingError, match='permission denied'):
            conn.execute(sqlalchemy.text(
                f"INSERT INTO {schema._quoted_name}.patient (case_id) VALUES ('abc')"
            ))


@use('db')
def test_domain_query_engine_is_cached_per_domain():
    engine = get_domain_query_engine('projectdbtest-cached')
    assert get_domain_query_engine('projectdbtest-cached') is engine
    assert get_domain_query_engine('projectdbtest-other') is not engine
    # Not ConnectionManager's engine, whose cache is unbounded
    assert connection_manager.get_engine(PROJECT_DB_ENGINE_ID) is not engine


# DEBUG/UNIT_TESTING off so the dev/test fallback doesn't supply project_db
@override_settings(REPORTING_DATABASES={'default': 'default'}, DEBUG=False, UNIT_TESTING=False)
def test_domain_query_engine_not_configured():
    with patch('corehq.apps.project_db.table_ddl.connection_manager', ConnectionManager()):
        with pytest.raises(ImproperlyConfigured, match='project_db'):
            get_domain_query_engine('projectdbtest-not-configured')


def test_case_table_basics():
    with patch.object(CaseTable, '_get_dd_properties', return_value=[
        ('nickname', 'plain'),
        ('favorite_color', 'select'),
        ('dob', 'date'),
        ('children_count', 'number'),
        ('location', 'gps'),
    ]):
        table = (CaseTable('test-domain', 'person')
                 .build_definition(sqlalchemy.MetaData()))

    assert table.name == 'person'
    assert table.schema == 'projectdb_test-domain'
    assert table.comment == 'person'  # raw case type, recoverable if truncated

    for column in CaseTable._static_columns():
        assert column.name in table.c

    assert isinstance(table.c['prop__nickname'].type, sqlalchemy.Text)
    assert isinstance(table.c['prop__favorite_color'].type, sqlalchemy.Text)
    assert isinstance(table.c['select_prop__favorite_color'].type, sqlalchemy.ARRAY)
    assert isinstance(table.c['select_prop__favorite_color'].type.item_type, sqlalchemy.Text)
    assert isinstance(table.c['prop__dob'].type, sqlalchemy.Text)
    assert isinstance(table.c['date_prop__dob'].type, sqlalchemy.Date)
    assert isinstance(table.c['prop__children_count'].type, sqlalchemy.Text)
    assert isinstance(table.c['number_prop__children_count'].type, sqlalchemy.Numeric)
    assert isinstance(table.c['prop__location'].type, sqlalchemy.Text)
    assert isinstance(table.c['gps_prop__location'].type, Earth)

    # Text property columns are NOT NULL; date/number/gps columns stay nullable,
    # but select columns are NOT NULL and default to an empty array
    assert table.c['prop__nickname'].nullable is False
    assert table.c['prop__dob'].nullable is False
    assert table.c['date_prop__dob'].nullable is True
    assert table.c['number_prop__children_count'].nullable is True
    assert table.c['gps_prop__location'].nullable is True
    assert table.c['select_prop__favorite_color'].nullable is False

    # Both plain and typed columns carry the raw property name as a comment
    assert table.c['prop__dob'].comment == 'dob'
    assert table.c['date_prop__dob'].comment == 'dob'
    assert table.c['prop__children_count'].comment == 'children_count'
    assert table.c['number_prop__children_count'].comment == 'children_count'
    assert table.c['gps_prop__location'].comment == 'location'
    assert table.c['select_prop__favorite_color'].comment == 'favorite_color'


def test_long_property_names_are_truncated():
    long_name = 'this_is_a_really_really_frankly_unreasonably_long_property_name'
    with patch.object(CaseTable, '_get_dd_properties', return_value=[(long_name, 'date')]):
        table = (CaseTable('test-domain', 'person').build_definition(sqlalchemy.MetaData()))

    plain_col = 'prop__this_is_a_really_really_frankly_unreasonably_lon_37418cd6'
    typed_col = 'date_prop__this_is_a_really_really_frankly_unreasonabl_2fd77f90'
    assert plain_col in table.c
    assert typed_col in table.c
    # The full property name remains recoverable via the column comment
    assert table.c[plain_col].comment == long_name
    assert table.c[typed_col].comment == long_name


def test_long_case_type_is_truncated():
    long_type = 'x' * 100
    case_table = CaseTable('test-domain', long_type)
    assert case_table.case_type == long_type
    assert case_table.table_name == truncate_identifier(long_type)

    with patch.object(CaseTable, '_get_dd_properties', return_value=[]):
        table = case_table.build_definition(sqlalchemy.MetaData())
    assert table.name == truncate_identifier(long_type)
    assert len(table.name.encode('utf-8')) <= 63
    assert table.comment == long_type


def _project_db_schema(domain):
    @fixture
    def inner():
        schema = DomainSchema(domain)
        try:
            yield schema
        finally:
            with get_project_db_engine().begin() as conn:
                schema.drop(conn)
    return inner()


@use('db')
def test_truncated_index_name():
    domain_schema = _project_db_schema('this-is-my-really-really-long-domain-name')
    table = Table(
        'fairly-long-table-name',
        sqlalchemy.MetaData(),
        sqlalchemy.Column('case_id', sqlalchemy.Text, primary_key=True),
        sqlalchemy.Column('owner_id', sqlalchemy.Text, index=True),
        schema=domain_schema.name,
    )
    # char limit is 64, this is 86
    assert list(table.indexes)[0].name == \
        'ix_projectdb_this-is-my-really-really-long-domain-name_fairly-long-table-name_owner_id'
    with get_project_db_engine().begin() as conn:
        domain_schema.create(conn)
        table.create(bind=conn)
        update_table(conn, table)  # this should no-op, not fail


@use('db', project_db_table('test-preview-drop', 'patient', {'first_name': 'plain'}))
def test_preview_drop_lists_tables_without_dropping():
    domain = 'test-preview-drop'
    notices = '\n'.join(preview_drop(domain))
    assert 'drop cascades to table "projectdb_test-preview-drop".patient' in notices
    with get_project_db_engine().begin() as conn:
        assert DomainSchema(domain).name in sqlalchemy.inspect(conn).get_schema_names()


@use('db')
@patch('corehq.apps.project_db.table_ddl._get_case_types')
@patch.object(CaseTable, '_get_dd_properties')
def test_create_project_db(get_dd_properties, get_case_types):
    # Actually commit the project_db definition to postgres and spot check results
    domain = 'test_create_project_db'
    schema = _project_db_schema('test_create_project_db')

    get_case_types.return_value = ['patient']
    get_dd_properties.return_value = [
        ('nickname', 'plain'), ('dob', 'plain'), ('interests', 'select')]
    create_or_update_project_db(domain)
    _assert_db_created_as_expected(schema.name)

    # Drop nickname, make dob a date, add a new prop
    get_dd_properties.return_value = [('favorite_color', 'plain'), ('dob', 'date')]
    create_or_update_project_db(domain)
    _assert_db_updated_as_expected(schema.name)


def _assert_db_created_as_expected(schema):
    with get_project_db_engine().begin() as conn:
        inspector = sqlalchemy.inspect(conn)
        assert schema in inspector.get_schema_names()
        assert ['patient'] == inspector.get_table_names(schema=schema)
        # The table stores the raw case type as a comment
        assert inspector.get_table_comment('patient', schema=schema) == {'text': 'patient'}

        cols = {col['name']: col for col in inspector.get_columns('patient', schema=schema)}
        col_types = {name: col['type'] for name, col in cols.items()}
        assert isinstance(col_types['case_name'], sqlalchemy.Text)
        assert isinstance(col_types['opened_on'], sqlalchemy.DateTime)
        assert isinstance(col_types['prop__nickname'], sqlalchemy.Text)
        assert isinstance(col_types['prop__dob'], sqlalchemy.Text)
        assert 'date_prop__dob' not in cols
        # A select property gets a text[] column that is NOT NULL, defaulting to {}
        assert isinstance(col_types['select_prop__interests'], sqlalchemy.ARRAY)
        assert cols['select_prop__interests']['nullable'] is False
        assert cols['select_prop__interests']['default'] == "'{}'::text[]"

        # Property columns store the raw case property name as a comment
        assert cols['prop__nickname']['comment'] == 'nickname'
        assert cols['prop__dob']['comment'] == 'dob'

        # Text property columns and external_id are NOT NULL, defaulting to ''
        for name in ['prop__nickname', 'prop__dob', 'external_id']:
            assert cols[name]['nullable'] is False, name
            assert cols[name]['default'] == "''::text", name
        # Other columns remain nullable
        assert cols['case_name']['nullable'] is True
        assert cols['parent_id']['nullable'] is True

        indexes = inspector.get_indexes('patient', schema=schema)
        assert any(ix['column_names'] == ['owner_id'] for ix in indexes)
        assert any(ix['column_names'] == ['parent_id'] for ix in indexes)


def _assert_db_updated_as_expected(schema):
    with get_project_db_engine().begin() as conn:
        inspector = sqlalchemy.inspect(conn)
        # still only the one table
        assert ['patient'] == inspector.get_table_names(schema=schema)

        columns = {col['name']: col for col in inspector.get_columns('patient', schema=schema)}
        # New column added, with its raw property name as a comment
        assert isinstance(columns['prop__favorite_color']['type'], sqlalchemy.Text)
        assert columns['prop__favorite_color']['comment'] == 'favorite_color'
        # Column for deleted case property is still present
        assert isinstance(columns['prop__nickname']['type'], sqlalchemy.Text)
        # Both a plain and a date column for dob
        assert isinstance(columns['prop__dob']['type'], sqlalchemy.Text)
        assert isinstance(columns['date_prop__dob']['type'], sqlalchemy.Date)


@use('db', project_db_table('test-reflect', 'patient', {
    'nickname': 'plain',
    'dob': 'date'
}))
def test_case_table_reflect():
    table = CaseTable('test-reflect', 'patient').reflect()
    assert table.name == 'patient'
    assert table.schema == 'projectdb_test-reflect'
    for column in CaseTable._static_columns():
        assert column.name in table.c
    assert isinstance(table.c['prop__nickname'].type, sqlalchemy.Text)
    assert isinstance(table.c['prop__dob'].type, sqlalchemy.Text)
    assert isinstance(table.c['date_prop__dob'].type, sqlalchemy.Date)
