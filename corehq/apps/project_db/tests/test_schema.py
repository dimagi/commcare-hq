import pytest
import sqlalchemy

from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.apps.project_db.schema import (
    build_table_for_case_type,
    build_tables_for_domain,
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

    def test_parent_relationship_adds_idx_column(self):
        table = build_table_for_case_type(
            self.metadata, 'test-domain', 'child',
            relationships=[('parent', 'parent_type')],
        )
        col = table.c['idx_parent']
        assert isinstance(col.type, sqlalchemy.Text)

    def test_multiple_relationships_add_all_columns(self):
        table = build_table_for_case_type(
            self.metadata, 'test-domain', 'child2',
            relationships=[
                ('parent', 'parent_type'),
                ('host', 'host_type'),
            ],
        )
        column_names = {col.name for col in table.columns}
        assert {'idx_parent', 'idx_host'} <= column_names

    def test_relationship_columns_have_no_foreign_keys(self):
        table = build_table_for_case_type(
            self.metadata, 'test-domain', 'child3',
            relationships=[('parent', 'parent_type')],
        )
        assert len(table.foreign_keys) == 0

    def test_relationship_columns_have_indexes(self):
        table = build_table_for_case_type(
            self.metadata, 'test-domain', 'child4',
            relationships=[('parent', 'parent_type')],
        )
        index_columns = set()
        for index in table.indexes:
            for col in index.columns:
                index_columns.add(col.name)
        assert 'idx_parent' in index_columns

    def test_relationship_index_naming(self):
        table = build_table_for_case_type(
            self.metadata, 'test-domain', 'child5',
            relationships=[('parent', 'parent_type')],
        )
        index_names = {idx.name for idx in table.indexes}
        expected_name = f'ix_{table.name}_idx_parent'
        assert expected_name in index_names

    def test_owner_id_has_index(self):
        index_names = {idx.name for idx in self.table.indexes}
        assert f'ix_{self.table.name}_owner_id' in index_names

    def test_modified_on_has_index(self):
        index_names = {idx.name for idx in self.table.indexes}
        assert f'ix_{self.table.name}_modified_on' in index_names


class TestNameValidation:

    def setup_method(self):
        self.metadata = sqlalchemy.MetaData()

    @pytest.mark.parametrize('name', [
        'has space',
        'semi;colon',
        'quote"mark',
        'paren(s)',
        'eq=ual',
    ])
    def test_invalid_property_name_raises(self, name):
        with pytest.raises(ValueError, match='Invalid property name'):
            build_table_for_case_type(
                self.metadata, 'test-domain', f'val_prop_{name[:4]}',
                properties=[(name, 'plain')],
            )

    @pytest.mark.parametrize('name', [
        'has space',
        'semi;colon',
        'quote"mark',
    ])
    def test_invalid_relationship_name_raises(self, name):
        with pytest.raises(ValueError, match='Invalid relationship name'):
            build_table_for_case_type(
                self.metadata, 'test-domain', f'val_rel_{name[:4]}',
                relationships=[(name, 'some_type')],
            )

    def test_valid_names_with_hyphens_and_underscores(self):
        table = build_table_for_case_type(
            self.metadata, 'test-domain', 'val_ok',
            properties=[('my-prop_1', 'plain')],
            relationships=[('my-rel_2', 'some_type')],
        )
        column_names = {col.name for col in table.columns}
        assert 'prop_my-prop_1' in column_names
        assert 'idx_my-rel_2' in column_names


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
        assert 'prop_village' in column_names
        assert 'prop_dob' in column_names
        assert 'prop_dob_date' in column_names

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
        assert 'prop_active_prop' in column_names
        assert 'prop_old_prop' not in column_names

    def test_relationships_produce_idx_columns(self):
        CaseType.objects.create(domain=SCHEMA_GEN_DOMAIN, name='child')

        metadata = sqlalchemy.MetaData()
        tables = build_tables_for_domain(
            metadata, SCHEMA_GEN_DOMAIN,
            relationships_by_type={
                'child': [('parent', 'parent_type')],
            },
        )

        table = tables['child']
        column_names = {col.name for col in table.columns}
        assert 'idx_parent' in column_names

    def test_multiple_relationships_produce_multiple_idx_columns(self):
        CaseType.objects.create(domain=SCHEMA_GEN_DOMAIN, name='referral')

        metadata = sqlalchemy.MetaData()
        tables = build_tables_for_domain(
            metadata, SCHEMA_GEN_DOMAIN,
            relationships_by_type={
                'referral': [
                    ('parent', 'patient'),
                    ('host', 'facility'),
                ],
            },
        )

        table = tables['referral']
        column_names = {col.name for col in table.columns}
        assert 'idx_parent' in column_names
        assert 'idx_host' in column_names

    def test_no_relationships_no_idx_columns(self):
        CaseType.objects.create(domain=SCHEMA_GEN_DOMAIN, name='standalone')

        metadata = sqlalchemy.MetaData()
        tables = build_tables_for_domain(metadata, SCHEMA_GEN_DOMAIN)

        table = tables['standalone']
        idx_columns = [
            col.name for col in table.columns if col.name.startswith('idx_')
        ]
        assert idx_columns == []

    def test_does_not_include_other_domains(self):
        CaseType.objects.create(domain='other-domain', name='person')

        metadata = sqlalchemy.MetaData()
        tables = build_tables_for_domain(metadata, SCHEMA_GEN_DOMAIN)

        assert 'person' not in tables
