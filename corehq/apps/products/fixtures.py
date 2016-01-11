from corehq.apps.products.models import Product
from corehq.apps.commtrack.fixtures import _simple_fixture_generator
from corehq.apps.products.models import SQLProduct
from corehq.apps.custom_data_fields.dbaccessors import get_by_domain_and_type

PRODUCT_FIELDS = [
    'name',
    'unit',
    'code',
    'description',
    'category',
    'program_id',
    'cost',
    'product_data'
]

CUSTOM_DATA_SLUG = 'product_data'


def product_fixture_generator_json(domain):
    if not SQLProduct.objects.filter(domain=domain).exists():
        return None

    fields = filter(lambda x: x != CUSTOM_DATA_SLUG, PRODUCT_FIELDS)
    fields.append('@id')

    custom_fields = get_by_domain_and_type(domain, 'ProductFields')
    if custom_fields:
        for f in custom_fields.fields:
            fields.append(CUSTOM_DATA_SLUG + '/' + f.slug)

    uri = 'jr://fixture/{}'.format(ProductFixturesProvider.id)
    return {
        'id': 'products',
        'uri': uri,
        'path': '/products/product',
        'name': 'Products',
        'structure': {
            f: {
                'name': f,
                'no_option': True
            } for f in fields},

        # DEPRECATED PROPERTIES
        'sourceUri': uri,
        'defaultId': 'products',
        'initialQuery': "instance('products')/products/product",
    }


class ProductFixturesProvider(object):
    id = 'commtrack:products'

    def __call__(self, user, version, last_sync=None, app=None):

        def get_products():
            return sorted(
                Product.by_domain(user.domain, include_archived=True),
                key=lambda product: product.code
            )

        return _simple_fixture_generator(
            user, self.id, "product", PRODUCT_FIELDS, get_products, last_sync
        )

product_fixture_generator = ProductFixturesProvider()
