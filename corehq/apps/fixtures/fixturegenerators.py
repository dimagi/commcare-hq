from collections import defaultdict
from xml.etree import ElementTree
from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType
from corehq.apps.users.models import CommCareUser
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
            'path': "/{tag}_list/{tag}".format(tag=data_type.tag),
            'name': data_type.tag,
            'structure': structure,

            # DEPRECATED PROPERTIES
            'sourceUri': uri,
            'defaultId': data_type.tag,
            'initialQuery': "instance('{tag}')/{tag}_list/{tag}".format(tag=data_type.tag),
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

    def __call__(self, user, version, last_sync=None):
        assert isinstance(user, CommCareUser)

        all_types = dict([(t._id, t) for t in FixtureDataType.by_domain(user.domain)])
        global_types = dict([(id, t) for id, t in all_types.items() if t.is_global])

        items_by_type = defaultdict(list)

        def _set_cached_type(item, data_type):
            # set the cached version used by the object so that it doesn't
            # have to do another db trip later
            item._data_type = data_type

        for global_fixture in global_types.values():
            items = list(FixtureDataItem.by_data_type(user.domain, global_fixture))
            _ = [_set_cached_type(item, global_fixture) for item in items]
            items_by_type[global_fixture._id] = items

        other_items = FixtureDataItem.by_user(user)
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
        all_types = data_types.values() + global_types.values()
        for data_type in all_types:
            xFixture = ElementTree.Element('fixture', attrib={'id': ':'.join((self.id, data_type.tag)),
                                                              'user_id': user.user_id})
            xItemList = ElementTree.Element('%s_list' % data_type.tag)
            xFixture.append(xItemList)
            for item in sorted(items_by_type[data_type.get_id], key=lambda x: x.sort_key):
                xItemList.append(item.to_xml())
            fixtures.append(xFixture)
        return fixtures

item_lists = ItemListsProvider()
