from __future__ import absolute_import
from __future__ import unicode_literals
from casexml.apps.phone.fixtures import FixtureProvider
from corehq.const import OPENROSA_VERSION_MAP
from corehq.apps.products.models import Product
from corehq.apps.commtrack.fixtures import simple_fixture_generator
from corehq.apps.fixtures.utils import get_index_schema_node
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

    fields = [x for x in PRODUCT_FIELDS if x != CUSTOM_DATA_SLUG]
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

        fixture_nodes = simple_fixture_generator(
            restore_user, self.id, "product", PRODUCT_FIELDS, get_products, restore_state.last_sync_log
        )
        if not fixture_nodes:
            return []

        if (restore_state.params.openrosa_version
                and restore_state.params.openrosa_version < OPENROSA_VERSION_MAP['INDEXED_PRODUCTS_FIXTURE']):
            # Don't include index schema when openrosa version is specified and below 2.1
            return fixture_nodes
        else:
            schema_node = get_index_schema_node(self.id, ['@id', 'code', 'program_id', 'category'])
            fixture_nodes[0].attrib['indexed'] = 'true'
            return [schema_node] + fixture_nodes


product_fixture_generator = ProductFixturesProvider()
