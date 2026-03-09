import pytest
import sqlalchemy

from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.apps.project_db.schema_gen import build_tables_for_domain

DOMAIN = 'test-schema-gen'


@pytest.mark.django_db
class TestBuildTablesForDomain:

    def test_returns_table_per_active_case_type(self):
        CaseType.objects.create(domain=DOMAIN, name='person')
        CaseType.objects.create(domain=DOMAIN, name='household')

        metadata = sqlalchemy.MetaData()
        tables = build_tables_for_domain(metadata, DOMAIN)

        assert set(tables.keys()) == {'person', 'household'}

    def test_empty_domain_returns_empty_dict(self):
        metadata = sqlalchemy.MetaData()
        tables = build_tables_for_domain(metadata, 'empty-domain')

        assert tables == {}

    def test_deprecated_case_types_excluded(self):
        CaseType.objects.create(domain=DOMAIN, name='active_type')
        CaseType.objects.create(
            domain=DOMAIN, name='old_type', is_deprecated=True,
        )

        metadata = sqlalchemy.MetaData()
        tables = build_tables_for_domain(metadata, DOMAIN)

        assert 'active_type' in tables
        assert 'old_type' not in tables

    def test_properties_become_columns(self):
        ct = CaseType.objects.create(domain=DOMAIN, name='patient')
        CaseProperty.objects.create(
            case_type=ct, name='village', data_type='plain',
        )
        CaseProperty.objects.create(
            case_type=ct, name='dob', data_type='date',
        )

        metadata = sqlalchemy.MetaData()
        tables = build_tables_for_domain(metadata, DOMAIN)

        table = tables['patient']
        column_names = {col.name for col in table.columns}
        assert 'prop_village' in column_names
        assert 'prop_dob' in column_names
        assert 'prop_dob_date' in column_names

    def test_deprecated_properties_excluded(self):
        ct = CaseType.objects.create(domain=DOMAIN, name='visit')
        CaseProperty.objects.create(
            case_type=ct, name='active_prop', data_type='plain',
        )
        CaseProperty.objects.create(
            case_type=ct, name='old_prop', data_type='plain',
            deprecated=True,
        )

        metadata = sqlalchemy.MetaData()
        tables = build_tables_for_domain(metadata, DOMAIN)

        table = tables['visit']
        column_names = {col.name for col in table.columns}
        assert 'prop_active_prop' in column_names
        assert 'prop_old_prop' not in column_names

    def test_does_not_include_other_domains(self):
        CaseType.objects.create(domain='other-domain', name='person')

        metadata = sqlalchemy.MetaData()
        tables = build_tables_for_domain(metadata, DOMAIN)

        assert 'person' not in tables
