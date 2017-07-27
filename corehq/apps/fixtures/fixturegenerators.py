from collections import defaultdict
from xml.etree import ElementTree

from casexml.apps.phone.fixtures import FixtureProvider
from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType
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
            'path': u"/{tag}_list/{tag}".format(tag=data_type.tag),
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

        all_types = {t._id: t for t in FixtureDataType.by_domain(restore_user.domain)}
        global_types = {id: t for id, t in all_types.items() if t.is_global}

        items_by_type = defaultdict(list)

        def _set_cached_type(item, data_type):
            # set the cached version used by the object so that it doesn't
            # have to do another db trip later
            item._data_type = data_type

        items = FixtureDataItem.by_data_types(restore_user.domain, global_types)
        for item in items:
            _set_cached_type(item, global_types[item.data_type_id])
            items_by_type[item.data_type_id].append(item)

        if set(all_types) - set(global_types):
            # only query ownership models if there are non-global types
            other_items = restore_user.get_fixture_data_items()

            for item in other_items:
                if item.data_type_id in global_types:
                    continue  # was part of the global type so no need to add here
                try:
                    _set_cached_type(item, all_types[item.data_type_id])
                except (AttributeError, KeyError):
                    continue
                items_by_type[item.data_type_id].append(item)

        fixtures = []
        types_sorted_by_tag = sorted(all_types.iteritems(), key=lambda (id_, type_): type_.tag)
        for data_type_id, data_type in types_sorted_by_tag:
            if data_type.is_indexed:
                fixtures.append(self._get_schema_element(data_type))
            items = sorted(items_by_type.get(data_type_id, []), key=lambda x: x.sort_key)
            fixtures.append(self._get_fixture_element(data_type, restore_user.user_id, items))
        return fixtures

    def _get_fixture_element(self, data_type, user_id, items):
        attrib = {
            'id': ':'.join((self.id, data_type.tag)),
            'user_id': user_id
        }
        if data_type.is_indexed:
            attrib['indexed'] = 'true'
        fixture_element = ElementTree.Element('fixture', attrib=attrib)
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
