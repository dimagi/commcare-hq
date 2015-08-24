def get_number_of_fixture_data_types_in_domain(domain):
    from corehq.apps.fixtures.models import FixtureDataType
    num_fixtures = FixtureDataType.get_db().view(
        'fixtures/data_types_by_domain',
        reduce=True,
        key=domain,
    ).first()
    return num_fixtures['value'] if num_fixtures is not None else 0


def get_fixture_data_types_in_domain(domain):
    from corehq.apps.fixtures.models import FixtureDataType
    return FixtureDataType.view(
        'fixtures/data_types_by_domain',
        key=domain,
        reduce=False,
        include_docs=True,
        descending=True,
    )


def get_owner_ids_by_type(domain, owner_type, data_item_id):
    from corehq.apps.fixtures.models import FixtureOwnership
    assert owner_type in FixtureOwnership.owner_type.choices, \
        "Owner type must be in {}".format(FixtureOwnership.owner_type.choices)
    return FixtureOwnership.get_db().view(
        'fixtures/ownership',
        key=[domain, '{} by data_item'.format(owner_type), data_item_id],
        reduce=False,
        wrapper=lambda r: r['value']
    )
