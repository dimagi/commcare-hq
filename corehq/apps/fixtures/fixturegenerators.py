from collections import defaultdict
from xml.etree import ElementTree
from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType
from casexml.apps.phone.models import OTARestoreUser
from corehq.apps.products.fixtures import product_fixture_generator_json
from corehq.apps.programs.fixtures import program_fixture_generator_json


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
            structure['@' + attr] = {
                'name': attr,
                'no_option': True
            }

        uri = 'jr://fixture/%s:%s' % (ItemListsProvider.id, data_type.tag)
        ret.append({
            'id': data_type.tag,
            'uri': uri,
            'path': u"/{tag}_list/{tag}".format(tag=data_type.tag),
            'name': data_type.tag,
            'structure': structure,

            # DEPRECATED PROPERTIES
            'sourceUri': uri,
            'defaultId': data_type.tag,
            'initialQuery': u"instance('{tag}')/{tag}_list/{tag}".format(tag=data_type.tag),
        })

    products = product_fixture_generator_json(domain)
    if products:
        ret.append(products)
    programs = program_fixture_generator_json(domain)
    if programs:
        ret.append(programs)
    return ret


class ItemListsProvider(object):
    id = 'item-list'

    def __call__(self, restore_user, version, last_sync=None, app=None):
        assert isinstance(restore_user, OTARestoreUser)

        all_types = {t._id: t for t in FixtureDataType.by_domain(restore_user.domain)}
        global_types = {id: t for id, t in all_types.items() if t.is_global}

        items_by_type = defaultdict(list)

        def _set_cached_type(item, data_type):
            # set the cached version used by the object so that it doesn't
            # have to do another db trip later
            item._data_type = data_type

        for global_fixture in global_types.values():
            items = FixtureDataItem.by_data_type(restore_user.domain, global_fixture)
            _ = [_set_cached_type(item, global_fixture) for item in items]
            items_by_type[global_fixture._id] = items

        other_items = restore_user.get_fixture_data_items()
        data_types = {}

        for item in other_items:
            if item.data_type_id in global_types:
                continue  # was part of the global type so no need to add here
            if item.data_type_id not in data_types:
                try:
                    data_types[item.data_type_id] = all_types[item.data_type_id]
                except (AttributeError, KeyError):
                    continue
            items_by_type[item.data_type_id].append(item)
            _set_cached_type(item, data_types[item.data_type_id])

        fixtures = []
        types_sorted_by_tag = sorted(all_types.iteritems(), key=lambda (id_, type_): type_.tag)
        for data_type_id, data_type in types_sorted_by_tag:
            items = items_by_type.get(data_type_id, [])
            fixtures.append(self._get_fixture_element(data_type.tag, restore_user.user_id, items))
        return fixtures

    def _get_fixture_element(self, tag, user_id, items):
        fixture_element = ElementTree.Element(
            'fixture',
            attrib={
                'id': ':'.join((self.id, tag)),
                'user_id': user_id
            }
        )
        item_list_element = ElementTree.Element('%s_list' % tag)
        fixture_element.append(item_list_element)
        for item in items:
            item_list_element.append(item.to_xml())
        return fixture_element


item_lists = ItemListsProvider()
