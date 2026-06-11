import pytest

from corehq.apps.project_db.schema import DomainSchema


def test_schema_name():
    assert DomainSchema('my-domain').name == 'projectdb_my-domain'


@pytest.mark.parametrize('domain, expected', [
    ('mydomain', 'projectdb_mydomain'),
    ('my-domain', '"projectdb_my-domain"'),
    ('my"domain', '"projectdb_my""domain"'),
])
def test_quoted_name(domain, expected):
    assert DomainSchema(domain)._quoted_name == expected
