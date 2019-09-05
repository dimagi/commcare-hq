from collections import defaultdict
from functools import partial
from operator import attrgetter
from xml.etree import cElementTree as ElementTree

from casexml.apps.phone.fixtures import FixtureProvider
from casexml.apps.phone.utils import (
    GLOBAL_USER_ID,
    get_or_cache_global_fixture,
)

from corehq.apps.fixtures.dbaccessors import iter_fixture_items_for_data_type
from corehq.apps.fixtures.models import FIXTURE_BUCKET, FixtureDataType
from corehq.apps.products.fixtures import product_fixture_generator_json
from corehq.apps.programs.fixtures import program_fixture_generator_json

from .utils import get_index_schema_node


def item_lists_by_domain(domain):
    ret = list()
    for data_type in FixtureDataType.by_domain(domain):
        structure = {
            f.field_name: {
                'name': f.field_name,
                'no_option': True
            } for f in data_type.fields
        }

        for attr in data_type.item_attributes:
            structure['@' + attr] = {'name': attr, 'no_option': True}

        uri = 'jr://fixture/%s:%s' % (ItemListsProvider.id, data_type.tag)
        ret.append({
            'id': data_type.tag,
            'uri': uri,
            'path': "/{tag}_list/{tag}".format(tag=data_type.tag),
            'name': data_type.tag,
            'structure': structure,
        })

    products = product_fixture_generator_json(domain)
    if products:
        ret.append(products)
    programs = program_fixture_generator_json(domain)
    if programs:
        ret.append(programs)
    return ret


class ItemListsProvider(FixtureProvider):
    id = 'item-list'

    def __call__(self, restore_state):
        restore_user = restore_state.restore_user
        global_types = {}
        user_types = {}
        for data_type in FixtureDataType.by_domain(restore_user.domain):
            if data_type.is_global:
                global_types[data_type._id] = data_type
            else:
                user_types[data_type._id] = data_type
        items = []
        if global_types:
            items.extend(self.get_global_items(global_types, restore_state))
        if user_types:
            items.extend(self.get_user_items(user_types, restore_user))
        return items

    def get_global_items(self, global_types, restore_state):
        domain = restore_state.restore_user.domain
        data_fn = partial(self._get_global_items, global_types, domain)
        return get_or_cache_global_fixture(restore_state, FIXTURE_BUCKET, '', data_fn)

    def _get_global_items(self, global_types, domain):
        def get_items_by_type(data_type):
            for item in iter_fixture_items_for_data_type(domain, data_type._id):
                self._set_cached_type(item, data_type)
                yield item

        return self._get_fixtures(global_types, get_items_by_type, GLOBAL_USER_ID)

    def get_user_items(self, user_types, restore_user):
        items_by_type = defaultdict(list)
        for item in restore_user.get_fixture_data_items():
            data_type = user_types.get(item.data_type_id)
            if data_type:
                self._set_cached_type(item, data_type)
                items_by_type[data_type].append(item)

        def get_items_by_type(data_type):
            return sorted(items_by_type.get(data_type, []),
                          key=attrgetter('sort_key'))

        return self._get_fixtures(user_types, get_items_by_type, restore_user.user_id)

    def _set_cached_type(self, item, data_type):
        # set the cached version used by the object so that it doesn't
        # have to do another db trip later
        item._data_type = data_type

    def _get_fixtures(self, data_types, get_items_by_type, user_id):
        fixtures = []
        for data_type in sorted(data_types.values(), key=attrgetter('tag')):
            if data_type.is_indexed:
                fixtures.append(self._get_schema_element(data_type))
            items = get_items_by_type(data_type)
            fixtures.append(self._get_fixture_element(data_type, user_id, items))
        return fixtures

    def _get_fixture_element(self, data_type, user_id, items):
        attrib = {
            'id': ':'.join((self.id, data_type.tag)),
            'user_id': user_id
        }
        if data_type.is_indexed:
            attrib['indexed'] = 'true'
        fixture_element = ElementTree.Element('fixture', attrib)
        item_list_element = ElementTree.Element('%s_list' % data_type.tag)
        fixture_element.append(item_list_element)
        for item in items:
            item_list_element.append(item.to_xml())
        return fixture_element

    def _get_schema_element(self, data_type):
        attrs_to_index = [field.field_name for field in data_type.fields if field.is_indexed]
        fixture_id = ':'.join((self.id, data_type.tag))
        return get_index_schema_node(fixture_id, attrs_to_index)


item_lists = ItemListsProvider()
