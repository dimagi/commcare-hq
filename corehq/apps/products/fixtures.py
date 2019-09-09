from distutils.version import LooseVersion

from casexml.apps.phone.fixtures import FixtureProvider

from corehq.apps.commtrack.fixtures import simple_fixture_generator
from corehq.apps.custom_data_fields.dbaccessors import get_by_domain_and_type
from corehq.apps.fixtures.utils import get_index_schema_node
from corehq.apps.products.models import SQLProduct
from corehq.const import OPENROSA_VERSION_MAP

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
        indexed = (
            not restore_state.params.openrosa_version
            or restore_state.params.openrosa_version >= LooseVersion(OPENROSA_VERSION_MAP['INDEXED_PRODUCTS_FIXTURE'])
        )

        fixture_nodes = self._get_fixture_items(restore_state, indexed)
        if not fixture_nodes:
            return []

        if not indexed:
            # Don't include index schema when openrosa version is specified and below 2.1
            return fixture_nodes
        else:
            schema_node = get_index_schema_node(self.id, ['@id', 'code', 'program_id', 'category'])
            return [schema_node] + fixture_nodes

    def _get_fixture_items(self, restore_state, indexed):
        restore_user = restore_state.restore_user

        project = restore_user.project
        if not project or not project.commtrack_enabled:
            return []

        if not self._should_sync(restore_state):
            return []

        data = list(
            SQLProduct.active_objects
            .filter(domain=restore_user.domain)
            .order_by('code')
            .all()
        )

        fixture_nodes = simple_fixture_generator(
            restore_user, self.id, "product", PRODUCT_FIELDS,
            data
        )
        if not fixture_nodes:
            return []

        if indexed:
            fixture_nodes[0].attrib['indexed'] = 'true'
        return fixture_nodes

    def _should_sync(self, restore_state):
        """
        Determine if a data collection needs to be synced.
        """
        last_sync = restore_state.last_sync_log
        if not last_sync:
            # definitely sync if we haven't synced before
            return True

        changes_since_last_sync = SQLProduct.objects.filter(
            domain=restore_state.restore_user.domain, last_modified__gte=last_sync.date
        ).exists()

        return changes_since_last_sync


product_fixture_generator = ProductFixturesProvider()
