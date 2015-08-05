from corehq.apps.fixtures.models import FixtureDataType


def get_number_of_fixture_data_types_in_domain(domain):
    num_fixtures = FixtureDataType.get_db().view(
        'domain/docs',
        startkey=[domain, 'FixtureDataType'],
        endkey=[domain, 'FixtureDataType', {}],
        reduce=True,
        group_level=2,
    ).first()
    return num_fixtures['value'] if num_fixtures is not None else 0


def get_fixture_data_types_in_domain(domain):
    return FixtureDataType.view(
        'domain/docs',
        endkey=[domain, 'FixtureDataType'],
        startkey=[domain, 'FixtureDataType', {}],
        reduce=False,
        include_docs=True,
        descending=True,
    )
