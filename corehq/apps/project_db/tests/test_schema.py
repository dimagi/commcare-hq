from corehq.apps.project_db.schema import get_project_db_table_name


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
