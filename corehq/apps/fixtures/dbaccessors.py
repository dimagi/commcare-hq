from corehq.apps.fixtures.models import FixtureDataType


def get_number_of_fixture_data_types_in_domain(domain):
    num_fixtures = FixtureDataType.get_db().view(
        'fixtures/data_types_by_domain',
        reduce=True,
        key=domain,
    ).first()
    return num_fixtures['value'] if num_fixtures is not None else 0


def get_fixture_data_types_in_domain(domain):
    return FixtureDataType.view(
        'fixtures/data_types_by_domain',
        key=domain,
        reduce=False,
        include_docs=True,
        descending=True,
    )
