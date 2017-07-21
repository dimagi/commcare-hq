from casexml.apps.phone.fixtures import FixtureProvider
from corehq.apps.products.models import Product
from corehq.apps.commtrack.fixtures import simple_fixture_generator
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
        'structure': {f: {'name': f, 'no_option': True} for f in fields},
    }


class ProductFixturesProvider(FixtureProvider):
    id = 'commtrack:products'

    def __call__(self, restore_state):
        restore_user = restore_state.restore_user

        def get_products():
            return sorted(
                Product.by_domain(restore_user.domain),
                key=lambda product: product.code
            )

        return simple_fixture_generator(
            restore_user, self.id, "product", PRODUCT_FIELDS, get_products, restore_state.last_sync_log
        )

product_fixture_generator = ProductFixturesProvider()
