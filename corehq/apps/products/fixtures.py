from corehq.apps.products.models import Product
from corehq.apps.commtrack.fixtures import _simple_fixture_generator


def product_fixture_generator(user, version, case_sync_op=None, last_sync=None):
    fields = [
        'name',
        'unit',
        'code',
        'description',
        'category',
        'program_id',
        'cost',
        'product_data'
    ]
    data_fn = lambda: Product.by_domain(user.domain, include_archived=True)
    return _simple_fixture_generator(user, "product", fields, data_fn, last_sync)
