from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.util.couch_helpers import paginate_view
from corehq.util.quickcache import quickcache
from corehq.util.test_utils import unit_testing_only


def get_number_of_fixture_data_types_in_domain(domain):
    from corehq.apps.fixtures.models import FixtureDataType
    num_fixtures = FixtureDataType.get_db().view(
        'by_domain_doc_type_date/view',
        startkey=[domain, 'FixtureDataType'],
        endkey=[domain, 'FixtureDataType', {}],
        reduce=True,
        group_level=2,
    ).first()
    return num_fixtures['value'] if num_fixtures is not None else 0


@quickcache(['domain'], timeout=30 * 60)
def get_fixture_data_types_in_domain(domain):
    from corehq.apps.fixtures.models import FixtureDataType
    return list(FixtureDataType.view(
        'by_domain_doc_type_date/view',
        endkey=[domain, 'FixtureDataType'],
        startkey=[domain, 'FixtureDataType', {}],
        reduce=False,
        include_docs=True,
        descending=True,
    ))


@quickcache(['domain', 'data_type_id'], timeout=60 * 60, memoize_timeout=60, skip_arg='bypass_cache')
def get_fixture_items_for_data_type(domain, data_type_id, bypass_cache=False):
    from corehq.apps.fixtures.models import FixtureDataItem
    return list(FixtureDataItem.view(
        'fixtures/data_items_by_domain_type',
        startkey=[domain, data_type_id],
        endkey=[domain, data_type_id, {}],
        reduce=False,
        include_docs=True,
    ))


def iter_fixture_items_for_data_type(domain, data_type_id):
    from corehq.apps.fixtures.models import FixtureDataItem
    for row in paginate_view(
            FixtureDataItem.get_db(),
            'fixtures/data_items_by_domain_type',
            chunk_size=1000,
            startkey=[domain, data_type_id],
            endkey=[domain, data_type_id, {}],
            reduce=False,
            include_docs=True
    ):
        yield FixtureDataItem.wrap(row['doc'])


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


@unit_testing_only
def delete_all_fixture_data_types():
    from corehq.apps.fixtures.models import FixtureDataType

    results = FixtureDataType.get_db().view('fixtures/data_types_by_domain_tag', reduce=False).all()
    for result in results:
        try:
            fixture_data_type = FixtureDataType.get(result['id'])
        except Exception:
            pass
        else:
            fixture_data_type.delete()
