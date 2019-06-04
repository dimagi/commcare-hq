from __future__ import absolute_import
from __future__ import unicode_literals
from collections import defaultdict
from operator import attrgetter
from xml.etree import cElementTree as ElementTree
from io import BytesIO

import six
from casexml.apps.phone.fixtures import FixtureProvider
from casexml.apps.phone.utils import ITEMS_COMMENT_PREFIX
from corehq.apps.fixtures.dbaccessors import iter_fixture_items_for_data_type
from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType, FIXTURE_BUCKET
from corehq.apps.products.fixtures import product_fixture_generator_json
from corehq.apps.programs.fixtures import program_fixture_generator_json
from corehq.blobs import CODES, get_blob_db
from corehq.blobs.models import BlobMeta
from corehq.blobs.exceptions import NotFound

from .utils import get_index_schema_node

# GLOBAL_USER_ID is expected to be a globally unique string that will never
# change and can always be search-n-replaced in global fixture XML. The UUID
# in this string was generated with `uuidgen` on Mac OS X 10.11.6
# HACK if this string is present anywhere in an item list it will be replaced
# with the restore user's user_id. DO NOT DEPEND ON THIS IMPLEMENTATION DETAIL.
# This is an optimization to avoid an extra XML parse/serialize cycle.
GLOBAL_USER_ID = 'global-user-id-7566F038-5000-4419-B3EF-5349FB2FF2E9'


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
        restore_user = restore_state.restore_user
        user_id = restore_user.user_id
        domain = restore_user.domain
        db = get_blob_db()
        if not restore_state.overwrite_cache:
            global_id = GLOBAL_USER_ID.encode('utf-8')
            b_user_id = user_id.encode('utf-8')
            try:
                data = db.get(key=FIXTURE_BUCKET + '/' + domain).read()
                return [data.replace(global_id, b_user_id)] if data else []
            except NotFound:
                pass
        global_items = self._get_global_items(global_types, domain)
        io = BytesIO()
        io.write(ITEMS_COMMENT_PREFIX)
        io.write(six.text_type(len(global_items)).encode('utf-8'))
        io.write(b'-->')
        for element in global_items:
            io.write(ElementTree.tostring(element, encoding='utf-8'))
            # change user_id AFTER writing to string for the cache
            element.attrib["user_id"] = user_id
        io.seek(0)
        try:
            kw = {"meta": db.metadb.get(
                parent_id=domain,
                type_code=CODES.fixture,
                name="",
            )}
        except BlobMeta.DoesNotExist:
            kw = {
                "domain": domain,
                "parent_id": domain,
                "type_code": CODES.fixture,
                "name": "",
                "key": FIXTURE_BUCKET + '/' + domain,
            }
        db.put(io, **kw)
        return global_items

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
        for data_type in sorted(data_types.values(), key=lambda data_type: data_type.tag):
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
