from collections import defaultdict
from xml.etree import ElementTree
from cStringIO import StringIO

from casexml.apps.phone.fixtures import FixtureProvider
from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType, FIXTURE_BUCKET
from corehq.apps.products.fixtures import product_fixture_generator_json
from corehq.apps.programs.fixtures import program_fixture_generator_json
from corehq.blobs import get_blob_db
from corehq.blobs.exceptions import NotFound

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
        global_types = {}
        user_types = {}
        for data_type in FixtureDataType.by_domain(restore_user.domain):
            if data_type.is_global:
                global_types[data_type._id] = data_type
            else:
                user_types[data_type._id] = data_type
        items = self.get_global_items(global_types, restore_state)
        items.extend(self.get_user_items(user_types, restore_user))
        return items

    def get_global_items(self, global_types, restore_state):
        restore_user = restore_state.restore_user
        domain = restore_user.domain
        db = get_blob_db()
        if not restore_state.overwrite_cache:
            try:
                fixture_data = db.get(domain, FIXTURE_BUCKET).read()
                return [fixture_data] if fixture_data else []
            except NotFound:
                pass
        global_items = self._get_global_items(global_types, restore_user)
        io = StringIO()
        for element in global_items:
            io.write(ElementTree.tostring(element, encoding='utf-8'))
        io.seek(0)
        db.put(io, domain, FIXTURE_BUCKET)
        return global_items

    def _get_global_items(self, global_types, restore_user):
        if not global_types:
            return []
        items_by_type = defaultdict(list)
        for item in FixtureDataItem.by_data_types(restore_user.domain, global_types):
            data_type = global_types[item.data_type_id]
            self._set_cached_type(item, data_type)
            items_by_type[data_type].append(item)
        return self._get_fixtures(global_types, items_by_type, restore_user.user_id)

    def get_user_items(self, user_types, restore_user):
        if not user_types:
            return []
        items_by_type = defaultdict(list)
        for item in restore_user.get_fixture_data_items():
            try:
                data_type = user_types[item.data_type_id]
            except KeyError:
                continue
            self._set_cached_type(item, data_type)
            items_by_type[data_type].append(item)
        return self._get_fixtures(user_types, items_by_type, restore_user.user_id)

    def _set_cached_type(self, item, data_type):
        # set the cached version used by the object so that it doesn't
        # have to do another db trip later
        item._data_type = data_type

    def _get_fixtures(self, data_types, items_by_type, user_id):
        def tag(item):
            data_type, items = item
            return data_type.tag

        def sort_key(item):
            return item.sort_key

        items_by_type = dict(items_by_type)
        for data_type in data_types.values():
            if data_type not in items_by_type:
                items_by_type[data_type] = []
        fixtures = []
        for data_type, items in sorted(items_by_type.items(), key=tag):
            if data_type.is_indexed:
                fixtures.append(self._get_schema_element(data_type))
            items = sorted(items, key=sort_key)
            fixtures.append(self._get_fixture_element(data_type, user_id, items))
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
